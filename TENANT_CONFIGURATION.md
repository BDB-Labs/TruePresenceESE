# Tenant Configuration Guide

This guide explains the configuration options available for each tenant, including how to customize detection rules, response thresholds, and add custom detectors.

## Configuration Philosophy

Our system uses a **tiered configuration approach** to balance security and flexibility:

### 🔒 TIER 1: Core Security Detectors (Non-Configurable)

These detectors are **always enabled** and cannot be disabled for security and legal compliance:

- `child_exploitation` - Detects child sexual abuse material discussions
- `illegal_content` - Detects illegal activities (drugs, weapons, etc.)

**Rationale**: These detectors protect against serious legal and ethical violations. Disabling them could expose your platform to legal liability.

### 📋 TIER 2: Policy Detectors (Client-Configurable)

These detectors can be **enabled, disabled, or customized** per tenant:

- `copyright_violation` - Detects copyright infringement discussions
- `torrent_sharing` - Detects torrent and file sharing links
- `crypto_mining` - Detects cryptocurrency mining discussions
- `remote_access` - Detects remote desktop/VNC access discussions

**Use Cases**:
- Media companies may want stricter copyright enforcement
- Tech communities may allow certain file sharing
- Gaming groups may disable crypto mining detection

### 🛠️ TIER 3: Custom Detectors (Enterprise Feature)

Available for enterprise clients with specific needs:
- Custom regex patterns
- Industry-specific detection rules
- Brand protection patterns

## Configuration Methods

### Method 1: Environment Variables (Recommended)

Set configuration via environment variables in your Railway deployment:

```bash
# Disable copyright detection for a tenant
DETECTOR_COPYRIGHT_VIOLATION_ENABLED_CLIENT1=false

# Adjust response thresholds
THRESHOLD_BAN_CLIENT1=0.9
THRESHOLD_KICK_CLIENT1=0.7

# Add custom patterns to torrent detector
DETECTOR_TORRENT_SHARING_PATTERNS_CLIENT1='["custom.*pattern.*here", "another.*pattern"]'
```

### Method 2: API Configuration (Dynamic)

Use the configuration API to adjust settings dynamically:

```bash
# Get current configuration
GET /telegram/config
Headers: X-Tenant-ID: client1

# Update configuration
POST /telegram/config/detectors
Headers: X-Tenant-ID: client1
Body: {
  "detectors": {
    "copyright_violation": {
      "enabled": false,
      "patterns": ["additional.*pattern.*if.*needed"]
    }
  },
  "response_thresholds": {
    "ban": 0.9,
    "kick": 0.7
  }
}
```

## Configuration Examples

### Example 1: Media Company (Strict Copyright)

```bash
# Environment variables
DETECTOR_COPYRIGHT_VIOLATION_ENABLED_MEDIACO=true
DETECTOR_TORRENT_SHARING_ENABLED_MEDIACO=true
THRESHOLD_BAN_MEDIACO=0.75
THRESHOLD_KICK_MEDIACO=0.6
```

**Effect**: More aggressive copyright enforcement with lower thresholds for action.

### Example 2: Tech Community (Relaxed File Sharing)

```bash
# Environment variables
DETECTOR_COPYRIGHT_VIOLATION_ENABLED_TECHCOMM=false
DETECTOR_TORRENT_SHARING_ENABLED_TECHCOMM=false
DETECTOR_CRYPTO_MINING_ENABLED_TECHCOMM=true
```

**Effect**: Allows file sharing discussions but still monitors for crypto mining.

### Example 3: Enterprise Client (Custom Patterns)

```bash
# Environment variables
CUSTOM_DETECTOR_ENTERPRISE_BRAND_PROTECTION_PATTERNS='["company.*secrets", "internal.*documents", "confidential.*data"]'
CUSTOM_DETECTOR_ENTERPRISE_BRAND_PROTECTION_ENABLED=true
```

**Effect**: Adds custom detection for internal brand protection.

## Response Threshold Configuration

Adjust confidence thresholds for different actions:

```bash
# Default thresholds
THRESHOLD_BAN=0.8      # Ban user
THRESHOLD_KICK=0.6     # Kick user  
THRESHOLD_REVIEW=0.4   # Manual review

# More aggressive (media company)
THRESHOLD_BAN_MEDIACO=0.7
THRESHOLD_KICK_MEDIACO=0.5

# More lenient (community group)
THRESHOLD_BAN_COMMUNITY=0.9
THRESHOLD_KICK_COMMUNITY=0.75
```

## Configuration Options Reference

### Available Configuration Parameters

| Parameter | Type | Default | Configurable | Description |
|-----------|------|---------|--------------|-------------|
| `DETECTOR_COPYRIGHT_VIOLATION_ENABLED` | boolean | `true` | ✅ | Enable copyright detection |
| `DETECTOR_TORRENT_SHARING_ENABLED` | boolean | `true` | ✅ | Enable torrent detection |
| `DETECTOR_CRYPTO_MINING_ENABLED` | boolean | `true` | ✅ | Enable crypto mining detection |
| `DETECTOR_REMOTE_ACCESS_ENABLED` | boolean | `true` | ✅ | Enable remote access detection |
| `THRESHOLD_BAN` | float | `0.8` | ✅ | Confidence for auto-ban |
| `THRESHOLD_KICK` | float | `0.6` | ✅ | Confidence for kick |
| `THRESHOLD_REVIEW` | float | `0.4` | ✅ | Confidence for manual review |
| `CUSTOM_DETECTOR_*_PATTERNS` | JSON array | `[]` | ✅ | Custom regex patterns |

### Configuration Validation Rules

1. **Core detectors cannot be disabled** via configuration
2. **Confidence thresholds** must be between 0.0 and 1.0
3. **Custom patterns** must be valid regex
4. **Tenant-specific variables** use `_{TENANT_ID}` suffix

## Best Practices

### Security Best Practices

1. **Never disable core detectors** - they protect against illegal content
2. **Review custom patterns** carefully to avoid false positives
3. **Start with default thresholds** and adjust based on real data
4. **Monitor changes** - log all configuration modifications

### Performance Best Practices

1. **Limit custom patterns** - each pattern adds processing overhead
2. **Use specific patterns** rather than broad ones
3. **Test patterns** before deploying to production
4. **Cache compiled regex** for better performance

### Compliance Best Practices

1. **Document your configuration** for audit purposes
2. **Maintain consistent policies** across similar clients
3. **Review configurations** periodically
4. **Get legal review** for custom detectors

## Migration Guide

### From Single-Tenant to Multi-Tenant

1. **Identify tenant requirements** - what configuration does each client need?
2. **Set up environment variables** for each tenant
3. **Test configurations** in staging environment
4. **Deploy gradually** - migrate clients one by one
5. **Monitor closely** - watch for unexpected behavior

### Configuration Versioning

```bash
# Add version to your configuration
CONFIG_VERSION_CLIENT1=v2.1
CONFIG_LAST_UPDATED_CLIENT1=2024-01-15
```

## Support & Troubleshooting

### Common Configuration Issues

**Issue: Configuration not applying**
- Check tenant ID spelling
- Verify environment variables are set
- Restart service after changes

**Issue: False positives increasing**
- Review custom patterns
- Adjust confidence thresholds
- Add exceptions to patterns

**Issue: Performance degradation**
- Reduce number of custom patterns
- Optimize regex expressions
- Check for pattern conflicts

### Getting Help

```bash
# Get available configuration options
GET /telegram/config/options

# Get current tenant configuration
GET /telegram/config
Headers: X-Tenant-ID: your_tenant

# Validate configuration before applying
POST /telegram/config/detectors
```

## Advanced Configuration

### Pattern Optimization

```python
# Instead of: r'.*bad.*word.*'
# Use: r'\bbad\s+word\b'  (more specific, faster)

# Instead of multiple similar patterns:
# r'word1', r'word2', r'word3'
# Use: r'word(1|2|3)'  (single compiled pattern)
```

### Conditional Configuration

```bash
# Environment-based configuration
if [ "$ENVIRONMENT" = "production" ]; then
  export THRESHOLD_BAN=0.85
else
  export THRESHOLD_BAN=0.75
fi
```

### Configuration Templates

Create reusable templates for common client types:

```yaml
# templates/strict.yaml
detectors:
  copyright_violation: {enabled: true}
  torrent_sharing: {enabled: true}
thresholds:
  ban: 0.75
  kick: 0.6

# templates/lenient.yaml
detectors:
  copyright_violation: {enabled: false}
  torrent_sharing: {enabled: false}
thresholds:
  ban: 0.9
  kick: 0.75
```

## Configuration Change Management

### Recommended Workflow

1. **Plan** - Document what you want to change and why
2. **Test** - Apply configuration in staging first
3. **Review** - Get team approval for changes
4. **Deploy** - Apply to production
5. **Monitor** - Watch for unexpected behavior
6. **Document** - Update your configuration records

### Change Log Example

```markdown
# Configuration Changes

## 2024-01-15 - Client1 Configuration Update

**Changes:**
- Disabled torrent_sharing detector
- Added custom pattern for brand protection
- Adjusted ban threshold from 0.8 to 0.85

**Reason:** Client requested more lenient file sharing policy while protecting brand mentions

**Approved by:** Security Team

**Monitoring:** Watch false positives for 7 days
```

## Enterprise Features

### Custom Detector Development

For enterprise clients, we offer:

1. **Custom pattern development** - We'll create optimized regex for your needs
2. **Industry-specific rules** - Pre-built configurations for your industry
3. **Brand protection** - Detect leaks of sensitive information
4. **Competitive intelligence** - Monitor competitor mentions

### Custom Detector Example

```json
{
  "custom_detectors": {
    "brand_protection": {
      "enabled": true,
      "patterns": [
        "company.*secrets",
        "internal.*documents",
        "confidential.*data",
        "proprietary.*information"
      ],
      "response": "immediate_ban",
      "notification": "legal_team"
    }
  }
}
```

## Legal Considerations

### Compliance Requirements

- **GDPR/CCPA**: Document all data processing activities
- **DMCA**: Maintain copyright enforcement records
- **Child Protection**: Never disable child exploitation detectors
- **Data Retention**: Follow local laws for log retention

### Audit Requirements

- Maintain configuration history
- Document rationale for changes
- Keep records of manual reviews
- Log all admin actions

## Summary

This configuration system provides:

✅ **Flexibility** - Customize for different client needs
✅ **Security** - Core protections always enabled
✅ **Compliance** - Audit trails and documentation
✅ **Performance** - Optimized pattern matching
✅ **Scalability** - Supports many tenants efficiently

**Need help?** Contact our support team for custom configuration assistance.
