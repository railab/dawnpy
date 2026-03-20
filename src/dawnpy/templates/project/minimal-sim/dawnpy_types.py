"""Placeholder type registration for ${PROJECT_NAME}."""

from dawnpy.descriptor.definitions.registry import TypeRegistration

# Keep a valid empty registration so `.dawnrc` can reference this file by
# default before the project grows custom IO / PROG / PROTO classes.
registration = TypeRegistration(name="${PROJECT_NAME}")
