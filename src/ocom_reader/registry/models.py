"""RegistryEntry — pointer-only representation of one indexed document.

"Pointer, not copy" (MILESTONE-007-DESIGN.md, MILESTONE-007.md): this
model deliberately has no field capable of holding document content,
a title, or a heading. It has exactly three fields: its own id, a
pointer to the RepositoryIndex entry it was built from, and a
classification. Anything else about the document — its title,
headings, preview — must be looked up through `document_id` via
RepositoryIndex; it is never copied here.
"""

from __future__ import annotations

from pydantic import BaseModel


class RegistryEntry(BaseModel):
    registry_id: str
    document_id: str
    entry_type: str
