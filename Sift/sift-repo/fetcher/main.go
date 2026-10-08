package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"syscall"
	"time"
)

var secret = []byte(os.Getenv("FETCH_SECRET"))

func blocked(ip net.IP) bool {
	if ip.IsLoopback() || ip.IsPrivate() || ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() ||
		ip.IsUnspecified() || ip.IsMulticast() || ip.IsInterfaceLocalMulticast() {
		return true
	}
	if v4 := ip.To4(); v4 != nil && (v4[0] == 0 || (v4[0] == 100 && v4[1]&0xC0 == 64)) {
		return true
	}
	return false
}

func control(network, address string, _ syscall.RawConn) error {
	host, port, err := net.SplitHostPort(address)
	if err != nil {
		return err
	}
	ip := net.ParseIP(host)
	if ip == nil || blocked(ip) {
		return errors.New("blocked address")
	}
	if port != "80" && port != "443" {
		return errors.New("blocked port")
	}
	return nil
}

type reqBody struct {
	URL string `json:"url"`
}

type result struct {
	Status      int    `json:"status"`
	FinalURL    string `json:"final_url"`
	ContentType string `json:"content_type"`
	XRobots     string `json:"x_robots"`
	Redirects   int    `json:"redirects"`
	Bytes       int    `json:"bytes"`
	Ms          int64  `json:"ms"`
	HTML        string `json:"html"`
}

func reply(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}

func handle(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		reply(w, 405, map[string]string{"error": "no"})
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 4096)
	var q reqBody
	if json.NewDecoder(r.Body).Decode(&q) != nil {
		reply(w, 400, map[string]string{"error": "bad"})
		return
	}
	m := hmac.New(sha256.New, secret)
	m.Write([]byte(q.URL))
	got, _ := hex.DecodeString(r.Header.Get("X-Sig"))
	if !hmac.Equal(got, m.Sum(nil)) {
		reply(w, 403, map[string]string{"error": "no"})
		return
	}
	u, err := url.Parse(q.URL)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Hostname() == "" || u.User != nil {
		reply(w, 400, map[string]string{"error": "bad url"})
		return
	}
	redirects := 0
	client := &http.Client{
		Timeout: 10 * time.Second,
		Transport: &http.Transport{
			Proxy:                 nil,
			DialContext:           (&net.Dialer{Timeout: 5 * time.Second, Control: control}).DialContext,
			DisableKeepAlives:     true,
			TLSHandshakeTimeout:   5 * time.Second,
			ResponseHeaderTimeout: 8 * time.Second,
		},
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			redirects++
			if redirects > 5 || (req.URL.Scheme != "http" && req.URL.Scheme != "https") {
				return http.ErrUseLastResponse
			}
			return nil
		},
	}
	req, _ := http.NewRequestWithContext(r.Context(), http.MethodGet, u.String(), nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; SiftBot/1.0)")
	req.Header.Set("Accept", "text/html,application/xhtml+xml")
	req.Header.Set("Accept-Language", "en")
	start := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		reply(w, 502, map[string]string{"error": "unreachable"})
		return
	}
	defer resp.Body.Close()
	out := result{Status: resp.StatusCode, FinalURL: resp.Request.URL.String(), ContentType: resp.Header.Get("Content-Type"),
		XRobots: resp.Header.Get("X-Robots-Tag"), Redirects: redirects}
	if ct := strings.ToLower(out.ContentType); strings.HasPrefix(ct, "text/html") || strings.HasPrefix(ct, "application/xhtml") {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
		out.Bytes = len(body)
		out.HTML = string(body)
	}
	out.Ms = time.Since(start).Milliseconds()
	reply(w, 200, out)
}

func main() {
	if len(secret) < 16 {
		panic("FETCH_SECRET must be at least 16 characters")
	}
	mux := http.NewServeMux()
	mux.HandleFunc("/fetch", handle)
	srv := &http.Server{Addr: ":9000", Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second,
		WriteTimeout: 20 * time.Second, MaxHeaderBytes: 8192}
	panic(srv.ListenAndServe())
}
