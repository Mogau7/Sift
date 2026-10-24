FROM golang:1.22-alpine AS b
RUN apk add --no-cache ca-certificates
WORKDIR /s
COPY go.mod main.go ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /fetcher .
FROM scratch
COPY --from=b /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=b /fetcher /fetcher
USER 65534:65534
ENTRYPOINT ["/fetcher"]
