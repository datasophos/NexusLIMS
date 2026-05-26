(compatibility)=
# Version Compatibility

This page documents the compatibility between NexusLIMS (backend) and
[NexusLIMS-CDCS](https://github.com/datasophos/NexusLIMS-CDCS) (frontend) versions.

```{important}
Using mismatched versions may cause upload failures or API errors. Always check this
table when upgrading either component.
```

## NexusLIMS-CDCS Version Tags

NexusLIMS-CDCS release tags follow the format `{base_cdcs_version}-nx{n}`, where the
`-nx{n}` suffix distinguishes NexusLIMS-specific releases from the upstream MDCS version.
For example, `3.20.0-nx0` is the first NexusLIMS release based on CDCS 3.20.0.

## NexusLIMS / NexusLIMS-CDCS Compatibility Matrix

| NexusLIMS Version | NexusLIMS-CDCS Version | Notes |
|-------------------|------------------------|-------|
| 2.6.1             | `3.20.x-nx0`           | CDCS REST API now requires trailing slashes on all endpoints; not backwards compatible with 3.18.x |
| 2.0 -- 2.6.0      | `3.18.0-nx0`           | |
| 1.x               | 2.x                    | Original NIST-era releases |
