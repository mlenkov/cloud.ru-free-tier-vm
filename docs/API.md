# 📡 API Documentation GitVerse VPS Fortify

## 📋 Overview

This document describes the APIs used by the GitVerse VPS Fortify system.

---

## 🔗 GitVerse API

### Base URL

```
https://gitverse.ru/api/v4
```

### Authentication

```
PRIVATE-TOKEN: <your-token>
```

### Endpoints

#### 1. Get Project

```bash
GET /projects/:id

# Example
curl -H "PRIVATE-TOKEN: $GITVERSE_TOKEN" \
  https://gitverse.ru/api/v4/projects/123
```

**Response**:
```json
{
  "id": 123,
  "name": "vps-fortify",
  "path": "user/vps-fortify",
  "default_branch": "main",
  "visibility": "private"
}
```

---

#### 2. Get File

```bash
GET /projects/:id/repository/files/:file_path?ref=:branch

# Example
curl -H "PRIVATE-TOKEN: $GITVERSE_TOKEN" \
  https://gitverse.ru/api/v4/projects/123/repository/files/config%2Fcis_standard.yaml?ref=main
```

**Response**:
```json
{
  "file_name": "cis_standard.yaml",
  "file_path": "config/cis_standard.yaml",
  "size": 1234,
  "encoding": "base64",
  "content": "BASE64_ENCODED_CONTENT",
  "ref": "main",
  "commit_id": "abc123",
  "last_commit_id": "def456"
}
```

---

#### 3. Update File

```bash
PUT /projects/:id/repository/files/:file_path

# Example
curl -X PUT -H "PRIVATE-TOKEN: $GITVERSE_TOKEN" \
  -F "branch=main" \
  -F "commit_message=Update config" \
  -F "content=@config/cis_standard.yaml" \
  https://gitverse.ru/api/v4/projects/123/repository/files/config%2Fcis_standard.yaml
```

**Response**:
```json
{
  "file_path": "config/cis_standard.yaml",
  "commit_id": "new_commit_hash",
  "branch": "main"
}
```

---

#### 4. Create Commit

```bash
POST /projects/:id/repository/commits

# Example
curl -X POST -H "PRIVATE-TOKEN: $GITVERSE_TOKEN" \
  -F "branch=main" \
  -F "commit_message=Update README" \
  -F "actions[0][action]=create" \
  -F "actions[0][file_path]=README.md" \
  -F "actions[0][content]=# Updated README" \
  https://gitverse.ru/api/v4/projects/123/repository/commits
```

**Response**:
```json
{
  "id": "new_commit_hash",
  "short_id": "abc1234",
  "title": "Update README",
  "created_at": "2024-01-15T10:30:00.000+00:00",
  "message": "Update README"
}
```

---

## 🔑 Bitwarden API

### Base URL

```
https://api.bitwarden.com
```

### Authentication

#### 1. Login

```bash
POST /identity/connect/token

# Request
{
  "grant_type": "password",
  "client_id": "mobile",
  "username": "user@email.com",
  "password": "your-password"
}

# Response
{
  "access_token": "jwt_token",
  "refresh_token": "refresh_token",
  "expires_in": 3600
}
```

#### 2. Unlock Vault

```bash
POST /identity/connect/token

# Request
{
  "grant_type": "refresh_token",
  "client_id": "mobile",
  "refresh_token": "refresh_token"
}

# Response
{
  "access_token": "jwt_token",
  "refresh_token": "new_refresh_token",
  "expires_in": 3600
}
```

---

### Endpoints

#### 1. Get Items

```bash
GET /items

# Headers
Authorization: Bearer <access_token>

# Example
curl -H "Authorization: Bearer $BW_ACCESS_TOKEN" \
  https://api.bitwarden.com/items
```

**Response**:
```json
{
  "data": [
    {
      "id": "item-id",
      "organizationId": null,
      "folderId": null,
      "type": 1,
      "name": "gitverse-credentials",
      "notes": null,
      "fields": [
        {
          "name": "token",
          "value": "gitverse-token-value",
          "type": 0,
          "reprompt": false
        }
      ]
    }
  ]
}
```

---

#### 2. Get Item

```bash
GET /items/:id

# Example
curl -H "Authorization: Bearer $BW_ACCESS_TOKEN" \
  https://api.bitwarden.com/items/item-id
```

**Response**:
```json
{
  "id": "item-id",
  "name": "gitverse-credentials",
  "fields": [
    {
      "name": "token",
      "value": "gitverse-token-value"
    }
  ]
}
```

---

#### 3. Create Item

```bash
POST /items

# Headers
Authorization: Bearer <access_token>

# Request
{
  "type": 1,
  "name": "gitverse-credentials",
  "fields": [
    {
      "name": "token",
      "value": "gitverse-token-value",
      "type": 0
    }
  ]
}

# Response
{
  "id": "new-item-id",
  "name": "gitverse-credentials"
}
```

---

#### 4. Update Item

```bash
PUT /items/:id

# Example
curl -X PUT -H "Authorization: Bearer $BW_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"gitverse-credentials","fields":[{"name":"token","value":"new-token"}]}' \
  https://api.bitwarden.com/items/item-id
```

---

## 🔄 Webhook Handler

### GitVerse Webhook

```python
# scripts/webhook_handler.py

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class GitVerseHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        event = json.loads(post_data)
        
        if event['event'] == 'push':
            # Trigger pipeline
            self.trigger_pipeline(event)
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    
    def trigger_pipeline(self, event):
        # Trigger CI/CD pipeline
        pass

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8080), GitVerseHandler)
    server.serve_forever()
```

---

## 📊 Metrics API

### Health Check

```bash
GET /health

# Response
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000+00:00",
  "version": "1.0.0"
}
```

---

### Compliance Status

```bash
GET /compliance/status

# Response
{
  "score": 95,
  "status": "compliant",
  "last_audit": "2024-01-15T10:30:00.000+00:00",
  "failed_checks": 0
}
```

---

## 🔐 Security

### Rate Limiting

- 100 requests per minute
- 1000 requests per hour

### Authentication

- JWT tokens (1 hour expiry)
- Refresh tokens (7 days expiry)

---

## 📚 Additional Resources

- [GitVerse API Docs](https://gitverse.ru/docs/api)
- [Bitwarden API Docs](https://bitwarden.com/help/api/)

---

*API Documentation generated by AI Employee*