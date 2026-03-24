(examples)=
# Examples

This page contains example code and configuration files for extending NexusLIMS.

## Instrument Profiles

### local_profile_example.py

{download}`Download example <examples/local_profile_example.py>`

A comprehensive, production-ready example of a local instrument profile that demonstrates:

- **Custom parser functions** - Add warnings, detect special acquisition modes, parse vendor-specific formats
- **Facility metadata injection** - Add consistent site-specific metadata to all files
- **Filename-based heuristics** - Detect data types from filename patterns
- **Static metadata** - Inject fixed values for all acquisitions
- **Best practices** - Proper logging, error handling, and documentation

**Use this example to:**

1. Create custom profiles for instruments unique to your facility
2. Understand the full capabilities of the InstrumentProfile system
3. Learn common patterns for metadata extraction customization

**How to use:**

1. Copy this file to your local profiles directory (configured via `NX_LOCAL_PROFILES_PATH`)
2. Change the `instrument_id` to match your instrument's name in the database
3. Customize the parser functions for your specific needs
4. Restart NexusLIMS - the profile will be automatically discovered and loaded

See the [Instrument Profiles](instrument_profiles.md) documentation for detailed information about creating and using instrument profiles.

## Contributing Examples

Have a useful example or pattern you'd like to share? Consider contributing it to this directory:

1. Ensure your example is well-documented with inline comments
2. Follow the existing code style and structure
3. Test your example thoroughly
4. Submit a pull request to the [NexusLIMS repository](https://github.com/datasophos/NexusLIMS)

Examples that demonstrate common use cases, best practices, or solve frequent challenges are especially welcome!
