# Findings

## Environment
- Windows 11, PowerShell primary. Project root: C:\web.projects\subjects (not a git repo yet).
- Need to verify: docker available locally? python 3.12? node?

## Spec anchors (docs/CAPTURE_APP_FABLE5_SPEC.md)
- Locked stack Section 2. Resolver contract Section 6.3. Prompts Appendix B. Schema Section 4.
- Auth: static bearer APP_TOKEN on /api/* writes + SSE.
- Ingest: 201 {id,status:'pending'} immediately, never block.
