(cdcs-customization)=
# Branding and Customization

This guide explains how to customize your NexusLIMS-CDCS deployment to match your organization's branding and requirements.

## Overview

NexusLIMS uses a centralized settings approach where all customization options are defined in `NexusLIMS-CDCS/config/settings/`.

This directory contains default values appropriate for development (`dev_settings.py`) and production (`prod_settings.py`) deployments of NexusLIMS. To customize your deployment, you can use the `custom_settings.py` template also provided in that folder.

### Customization Workflow

1. **Never modify:**
   - `nexuslims_overrides/settings.py`
   - `config/settings/dev_settings.py`
   - `config/settings/prod_settings.py`
2. **Override/change settings** in `config/settings/custom_settings.py`
3. **Update `DJANGO_SETTINGS_MODULE`** in your `.env` file by setting it to `DJANGO_SETTINGS_MODULE=config.settings.custom_settings`
4. **Place custom assets** (logos, images) in `config/static_files/`
5. **Restart containers** to load new configuration (no rebuild required)

---

## Branding & Logos

### Navigation Bar Logo

The logo displayed in the top-left corner of the navigation bar.

```python
# Default: "nexuslims/img/logo_horizontal_light.png"
NX_NAV_LOGO = "path/to/your/logo_horizontal_light.png"
```

**Recommendations:**
- **Format**: PNG with transparent background
- **Size**: Max height ~24px
- **Aspect ratio**: Horizontal logos work best (2:1 to 4:1)

### Footer Logo

The logo displayed in the footer.

```python
# Default: "nexuslims/img/datasophos_logo.png"
NX_FOOTER_LOGO = "path/to/your/footer_logo.png"

# Default: "https://datasophos.co"
NX_FOOTER_LINK = "https://your-organization.com"
```

### Homepage Logo

The logo displayed on the homepage alongside the welcome text.

```python
# Default: "nexuslims/img/logo_stacked_modern.png"
NX_HOMEPAGE_LOGO = "path/to/your/homepage_logo.png"
```

**Recommendations:**
- **Format**: PNG or SVG
- **Size**: Max width 400px
- **Style**: Can include text/wordmark

---

## Theme Colors

Customize the color scheme of your NexusLIMS deployment using CSS custom properties. These colors are used throughout the interface for buttons, links, badges, and other UI elements.

```python
NX_THEME_COLORS = {
    "primary": "#11659c",           # Main brand color (buttons, links, icons)
    "primary_dark": "#0d528a",      # Darker variant for hover states
    "info_badge_dark": "#505050",   # Info badge background color
    "secondary": "#f9f9f9",         # Secondary (light) button background
    "secondary_dark": "#e2e2e2",    # Secondary button hover state
    "success": "#28a745",           # Success states
    "danger": "#dc3545",            # Error/danger states
    "warning": "#ffc107",           # Warning states and hover highlights
    "info": "#17a2b8",              # Info messages
    "light_gray": "#e3e3e3",        # Light gray accents
    "dark_gray": "#212529",         # Dark text color
}
```

**How it works:**
- Colors are injected as CSS custom properties (e.g., `--nx-primary-color`)
- Only specify colors you want to change; unspecified colors use CSS defaults
- Changes take effect after restarting the Django container

**Usage:**
- Set `NX_THEME_COLORS` in your `config/settings/custom_settings.py`
- Only include the colors you want to override

**Example: Custom Blue Theme**
```python
NX_THEME_COLORS = {
    "primary": "#1a5276",
    "primary_dark": "#154360",
    "warning": "#f4d03f",
}
```

**Example: Corporate Green Theme**
```python
NX_THEME_COLORS = {
    "primary": "#1e8449",
    "primary_dark": "#196f3d",
    "info_badge_dark": "#2c3e50",
}
```

```{tip}
Choose a primary color that represents your organization's brand. The `warning` color is used for hover highlights on links and buttons.
```

---

## Homepage Content

### Welcome Title

```python
# Default: "Welcome to NexusLIMS!"
CUSTOM_TITLE = "Welcome to Your LIMS!"
```

### Homepage Text

```python
NX_HOMEPAGE_TEXT = """
Your custom introductory text here. This appears on the homepage
and explains what your LIMS does and how to use it.
"""
```

```{tip}
Keep this concise (2-3 sentences) and action-oriented.
```

### Documentation Link

```python
# Default: "https://datasophos.github.io/NexusLIMS/"
NX_DOCUMENTATION_LINK = "https://docs.your-organization.com"
```

Set to empty string `""` to hide the documentation link entirely.

---

## Navigation Menu

### Custom Menu Links

Add custom links to the top navigation bar.

```python
NX_CUSTOM_MENU_LINKS = [
    {
        "title": "Data Portal",
        "url": "https://portal.your-org.com",
        "icon": "database",           # Font Awesome icon name (optional)
        "iconClass": "fas"            # Font Awesome class (optional)
    },
    {
        "title": "Help Desk",
        "url": "https://help.your-org.com",
        "icon": "question-circle"
    },
    {
        "title": "Team Directory",
        "url": "/team",
        "icon": "users"
    },
]
```

**Icon Options:**
- Use any [Font Awesome 6](https://fontawesome.com/v6/search) icon name
- `iconClass` can be `"fas"` (solid), `"far"` (regular), or `"fab"` (brands)
- Omit `icon` to display text only

```{tip}
Limit to 3-5 custom links to avoid cluttering the navigation.
```

---

## XSLT Configuration

### XSLT Debug Mode

Enable detailed messages from XSLT transformation for debugging.

```python
# Enable XSLT debug output (default: False)
NX_XSLT_DEBUG = True
```

**Use Cases:**
- **Development**: Set to `True` when working on XSLT stylesheets
- **Production**: Set to `False` to avoid verbose debug output

You can add debug statements in XSLT using `<xsl:message>` tags:

```xml
<xsl:message>DEBUG: Processing instrument <xsl:value-of select="$instrument-name"/></xsl:message>
```

### Instrument Badge Colors

Configure colors for instrument badges in detail and list views.

```python
NX_INSTRUMENT_COLOR_MAPPINGS = {
    "FEI-Titan-TEM": "#2E86AB",     # Blue for TEMs
    "FEI-Titan-STEM": "#0645AD",    # Darker blue for STEM
    "FEI-Quanta200-ESEM": "#A569BD", # Purple for ESEM
    "Hitachi-S4700-SEM": "#E74C3C", # Red for Hitachi SEMs
    "JEOL-JSM7100-SEM": "#F39C12",  # Orange for JEOL SEMs
    "Zeiss-LEO_1525_FESEM": "#16A085", # Teal for Zeiss
}
```

**Best Practices:**
- Use distinct, accessible colors
- Choose colors that contrast well with white text
- Group similar instruments by color family
- Use tools like [Coolors](https://coolors.co/) for palettes

---

## Feature Flags

### Enable/Disable Features

```python
# Enable the interactive tutorial (default: True)
NX_ENABLE_TUTORIALS = True
```

### Dataset Display Threshold

Control when simplified display mode is used for records with many datasets.

```python
# Records with more datasets than this use simple display
# Default: 100
NX_MAX_DATASET_DISPLAY_COUNT = 100
```

**Guidelines:**
- **Default (100)**: Records with 101+ datasets use simple display
- **Lower values (50)**: More records use simple display (better performance)
- **Higher values (500)**: Fewer records use simple display (more interactive)
- **0**: Always use full interactive display

---

## Custom Assets

### Directory Structure

Place custom assets in `config/static_files/`:

```text
config/
├── static_files/
│   ├── logo_horizontal_light.png
│   ├── footer_logo.png
│   ├── logo_horizontal_text.png
│   └── custom_icon.png
└── settings/
    └── custom_settings.py
```

**Benefits:**
- Keep customizations separate from app code
- No need to modify `nexuslims_overrides/` directory
- Runtime configuration updates without rebuilding containers

---

## Example Configurations

### University Deployment

```python
# University of Example - NexusLIMS Settings

# Theme Colors (university blue)
NX_THEME_COLORS = {
    "primary": "#2E86AB",
    "primary_dark": "#1A5276",
    "warning": "#F5B041",
}

# Branding
CUSTOM_TITLE = "Welcome to UEx Microscopy LIMS"
NX_NAV_LOGO = "nexuslims/img/uex_nav_logo.png"
NX_FOOTER_LOGO = "nexuslims/img/uex_footer_logo.png"
NX_FOOTER_LINK = "https://microscopy.uex.edu"

# Content
NX_HOMEPAGE_TEXT = (
    "Access and manage microscopy data from the University of Example "
    "Microscopy Core Facility."
)
NX_DOCUMENTATION_LINK = "https://microscopy.uex.edu/docs"

# Navigation
NX_CUSTOM_MENU_LINKS = [
    {"title": "Core Facility", "url": "https://microscopy.uex.edu", "icon": "microscope"},
    {"title": "Book Time", "url": "https://booking.uex.edu", "icon": "calendar"},
    {"title": "Training", "url": "https://training.uex.edu", "icon": "graduation-cap"},
]

# Instrument Colors
NX_INSTRUMENT_COLOR_MAPPINGS = {
    "FEI-Titan-TEM": "#2E86AB",
    "FEI-Titan-STEM": "#0645AD",
    "FEI-Quanta200-ESEM": "#A569BD",
}

# Features
NX_ENABLE_TUTORIALS = True
NX_MAX_DATASET_DISPLAY_COUNT = 99
```

### Corporate Lab

```python
# Acme Corp - Materials Lab LIMS Settings

# Theme Colors (corporate orange)
NX_THEME_COLORS = {
    "primary": "#E67E22",
    "primary_dark": "#D35400",
    "info_badge_dark": "#34495E",
}

# Branding
CUSTOM_TITLE = "Acme Materials Lab"
NX_NAV_LOGO = "nexuslims/img/acme_logo_white.png"
NX_FOOTER_LOGO = "nexuslims/img/acme_logo_color.png"
NX_FOOTER_LINK = "https://acme.com/materials-lab"

# Content
NX_HOMEPAGE_TEXT = (
    "Materials characterization data management system for Acme Corp R&D."
)
NX_DOCUMENTATION_LINK = ""  # Internal docs not public

# Navigation
NX_CUSTOM_MENU_LINKS = [
    {"title": "Sample Request", "url": "https://samples.acme.internal", "icon": "flask"},
    {"title": "Lab Wiki", "url": "https://wiki.acme.internal/materials", "icon": "book"},
    {"title": "Support", "url": "mailto:lab-support@acme.com", "icon": "envelope"},
]

# Features
NX_ENABLE_TUTORIALS = False  # Custom onboarding
NX_MAX_DATASET_DISPLAY_COUNT = 249
```

---

## Troubleshooting

### Changes Not Appearing

1. **Restart Django**:
   ```bash
   dc-prod restart cdcs
   ```

2. **Run collectstatic**:
   ```bash
   docker exec nexuslims_prod_cdcs python manage.py collectstatic --noinput
   ```

3. **Clear browser cache**: Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)

### Instrument Colors Not Updating

1. Verify setting name is exactly `NX_INSTRUMENT_COLOR_MAPPINGS`
2. Check instrument PIDs match exactly what's in the database
3. Validate color format (must be `#RRGGBB`)
4. Restart Django (XSLT parameters load at startup)
5. Enable `NX_XSLT_DEBUG = True` to see transformation messages

### Logo Not Displaying

- Check file path is correct (relative to `config/static_files/`)
- Verify file exists and has read permissions
- Run `collectstatic` to collect files
- Check Django logs for 404 errors

### Menu Links Not Showing

- Verify `NX_CUSTOM_MENU_LINKS` is a list of dictionaries
- Each dict must have `"title"` and `"url"` keys
- Restart Django after settings changes

### Theme Colors Not Applying

If your custom theme colors aren't appearing:

1. Verify dictionary keys are lowercase without `nx_` prefix (e.g., `"primary"`, not `"NX_PRIMARY_COLOR"`)
2. Check color format is valid CSS (e.g., `#RRGGBB`)
3. Restart Django (theme colors load at startup)
4. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)

**Valid keys:** `primary`, `primary_dark`, `info_badge_dark`, `secondary`, `secondary_dark`, `success`, `danger`, `warning`, `info`, `light_gray`, `dark_gray`

---

## Summary

NexusLIMS customization is designed to be:

- **Centralized**: All settings in one place
- **Safe**: Override in your settings, never modify defaults
- **Flexible**: From simple logo swaps to complete rebranding
- **Maintainable**: Clearly separated from core CDCS code

Start with basic branding (logos and text), then progressively customize navigation, features, and styling as needed.
