# Using curl for API Testing

This guide covers how to use curl to test REST APIs.

## GET Requests

```bash
curl https://api.example.com/users
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/me
```

## POST Requests

To send JSON data:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"name": "test"}' https://api.example.com/users
```

## Environment Variables

Store your API base URL in a variable:

```bash
export API_URL="https://api.example.com"
curl $API_URL/health
```

## Downloading Files

```bash
curl -O https://example.com/file.tar.gz
```

## Debugging

Use the `-v` flag for verbose output:

```bash
curl -v https://api.example.com/debug
```
