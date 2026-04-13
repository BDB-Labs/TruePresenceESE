# Multi-Tenancy Setup Guide for TruePresence

This guide explains how to set up and configure multiple isolated instances of the TruePresence system for different clients, ensuring complete data privacy and isolation.

## Architecture Overview

The system now supports **multi-tenancy**, meaning:

- **Complete Data Isolation**: Each client's data is completely separate
- **Privacy Compliance**: No cross-contamination between different instances
- **Independent Configuration**: Each tenant can have different bot tokens and settings
- **Scalable**: Handles multiple concurrent clients efficiently

## Setup Options

### Option 1: Single Deployment with Multiple Tenants (Recommended)

This approach runs one instance of the service but isolates data by tenant ID.

#### Configuration

1. **Environment Variables**:

```bash
# Default tenant
TELEGRAM_BOT_TOKEN=your_default_bot_token

# Client-specific tenants
TELEGRAM_BOT_TOKEN_CLIENT1=client1_bot_token
TENANT_NAME_CLIENT1="Client 1 Production"

TELEGRAM_BOT_TOKEN_CLIENT2=client2_bot_token  
TENANT_NAME_CLIENT2="Client 2 Production"

# Base URL for admin notifications
BASE_URL=https://your-domain.com
```

2. **Tenant Identification**:

Tenants are identified by:
- `X-Tenant-ID` header in API requests
- Query parameter `?tenant=client1` in webhook URLs
- Custom logic in your integration

#### API Endpoints with Multi-Tenancy

All endpoints now support tenant isolation:

```bash
# Register a group for a specific tenant
POST /groups/{group_id}/protect?tenant=client1

# Get status for a specific tenant
GET /status
Headers: X-Tenant-ID: client1

# Get all reviews for a tenant
GET /reviews
Headers: X-Tenant-ID: client1

# Resolve a review for a tenant
POST /reviews/{id}/resolve
Headers: X-Tenant-ID: client1
```

### Option 2: Separate Deployments (Maximum Isolation)

For maximum security and isolation, you can deploy separate instances:

```bash
# Client 1 deployment
docker run -e TELEGRAM_BOT_TOKEN=client1_token -e TENANT_ID=client1 truepresence

# Client 2 deployment  
docker run -e TELEGRAM_BOT_TOKEN=client2_token -e TENANT_ID=client2 truepresence
```

## Webhook Configuration

### Single Deployment with Tenant Routing

```bash
# Webhook URL format
https://your-domain.com/webhook?tenant=client1

# Or using headers
curl -X POST https://your-domain.com/webhook \
  -H "X-Tenant-ID: client1" \
  -H "Content-Type: application/json" \
  -d '{"update_id": 123, "message": {...}}'
```

### Separate Deployments

```bash
# Client 1 webhook
https://client1.your-domain.com/webhook

# Client 2 webhook
https://client2.your-domain.com/webhook
```

## Admin Notification Setup

Admin notifications are sent to Telegram chats configured for each tenant:

```python
# Register admin chat for a tenant
service.register_group(group_id, admin_chat_id=ADMIN_CHAT_ID, tenant_id="client1")
```

Each tenant's admins only see reviews for their own tenant.

## Database Considerations

For production use with persistent storage:

1. **Redis Configuration**:
   - Use separate Redis databases for each tenant
   - Or use key prefixes: `tenant1:reviews`, `tenant2:reviews`

2. **PostgreSQL Configuration**:
   - Separate schemas per tenant
   - Or separate databases

## Privacy and Security

### Data Isolation Guarantees

- ✅ **Session Data**: Each tenant has separate user sessions
- ✅ **Review Data**: Manual reviews are tenant-isolated
- ✅ **Admin Access**: Admins only see their tenant's data
- ✅ **Bot Tokens**: Each tenant can have different bot credentials
- ✅ **API Isolation**: Tenant ID required for all operations

### Security Best Practices

1. **API Authentication**:
   - Use API keys with tenant scoping
   - Implement JWT with tenant claims

2. **Rate Limiting**:
   - Apply per-tenant rate limits

3. **Audit Logging**:
   - Log all admin actions with tenant context

## Deployment Checklist

### For Railway Deployment

1. **Set environment variables**:
   ```bash
   railway variables set TELEGRAM_BOT_TOKEN=your_token
   railway variables set TELEGRAM_BOT_TOKEN_CLIENT1=client1_token
   railway variables set BASE_URL=https://your-app.up.railway.app
   ```

2. **Configure webhook URLs**:
   ```bash
   # For each tenant
   curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://your-app.up.railway.app/webhook?tenant=client1"
   ```

3. **Register admin chats**:
   ```bash
   # Call the protect endpoint for each group
   POST /groups/12345/protect?tenant=client1&admin_chat_id=99999
   ```

### For Docker Deployment

```yaml
# docker-compose.override.yml
version: '3.8'

services:
  truepresence:
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_BOT_TOKEN_CLIENT1=${TELEGRAM_BOT_TOKEN_CLIENT1}
      - TELEGRAM_BOT_TOKEN_CLIENT2=${TELEGRAM_BOT_TOKEN_CLIENT2}
      - BASE_URL=${BASE_URL}
```

## Monitoring and Management

### Multi-Tenant Status

```bash
# Get status for all tenants
GET /status?all=true

# Get status for specific tenant
GET /status
Headers: X-Tenant-ID: client1
```

### Admin Dashboard Integration

Create admin interfaces that:
1. Show tenant selector
2. Filter data by tenant ID
3. Respect tenant boundaries

## Troubleshooting

### Common Issues

**Issue: "Tenant not found"**
- Solution: Initialize tenant by calling `register_group` first

**Issue: Cross-tenant data access**
- Solution: Verify `X-Tenant-ID` headers are being sent

**Issue: Admin not receiving notifications**
- Solution: Check tenant-specific bot token configuration

## Migration from Single-Tenant

If upgrading from previous version:

1. **Backup your data**
2. **Update configuration** to include tenant IDs
3. **Test thoroughly** with different tenant scenarios
4. **Monitor logs** for tenant-related messages

## Support

For multi-tenancy specific issues, check:
- Logs for `[tenant_id]` prefixes
- Tenant isolation in Redis/Postgres
- Header propagation in your API gateway

The system is designed to fail safely - if tenant ID is missing, it defaults to "default" tenant while logging warnings.