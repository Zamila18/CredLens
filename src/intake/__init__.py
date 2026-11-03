"""Records entered through the demo workflow: consent, visits, applications.

Every function here checks the rules first (synthetic-only mode, the demo calendar,
consent, one application per merchant) and then writes the record, its provenance and
its audit entry in one transaction. The API calls these; it does not write the rows itself.
"""
