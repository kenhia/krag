# krager observations

## Modifications

It works, but we can make it better.

### General

- [ ] After initially connecting to kragd, upon restart it should prepopulate the connect info (host and port)
    to whatever was used for the last successful connection (see also KM002 as a place to save this)
- [ ] Do we have a config for `krager` (on the local machine where the remote client is running)? If not we
    likely need one.
- [ ] We should have a settings control in the left nav and page where we can adjust all/most settings we add;
    Any non-default values should be saved to the config and then loaded on startup.
- [ ] Opacity should be configurable.

### Query

- [ ] Query window does not expose the same level of control as CLI
    - top-k : no way to set
    - preset : no way to set
    - mode : present
    - no-synthesis : present as "Retrieve Only"
    - format : N/A - we want JSON only
    - debug : no way to set; somewhat covered by the debug page
    - sources/no-sources : no way to set
    - host/port : covered by connection
    - help : N/A
- [ ] Query should also have critic controls (this may require a bit of re-architecture?)
    - enable/disable checkbox
    - cut-off score to apply

#### Query Transcript
- [x] Transcript - New items are added below older items, this feels counter-intuitive and you have to search to find
      the answer.
      > **FIXED**: T080 — Reversed transcript display order, newest entries now appear at top.
- [ ] Chunks are prominent. Having the chunks gives an insight into why the LLM can/cannot answer, but they make looking
      at answer and sources difficult.
- [ ] Thinking we should move transcript to it's own page and show the current answer on the query page with a list of
      sources and (if applicable) debug information but no chunks. Chunks remain on the transcript page.

### Index
- [ ] Only allows configured source with Incremental or Full run. This is probably the right choice for now, future
    enhancement should allow select/deselect of configured paths from the kragd config.

### System
- [ ] Embedding models only lists "BAAI/bge-base-en-v1.5"; not "jinaai/jina-embeddings-v2-base-code"


## Bugs and Issues

- [x] Connection timeout (there may already be one?). I forgot to enter the connection info, so it was trying to 
    connect to non-existent localhost and kept trying to connect until I shut it off and restarted. This only seems to
    be an issue with "localhost" as the hostname.
    > **FIXED**: T078 — Added 15s AbortController timeout to `getHealth()`. Prevents infinite connection loop.
- [x] Got a "Connect reach kragd:8742 - error sending request for url (http://kragd:8742/health)" error; I had
    incorrectly entered "kragd" instead of "karch9", but when it got this error, the connection host box became small
    and you couldn't see the text (subsequent "playing" showed the text was still in the box), but the small box made
    the text "disappear". This seems to be caused by the error taking up over half of the size of the window and
    "squishing" the host text box; maximizing the window "fixes" this, but it's not a good user experience. We should
    keep a minimum size for the host text so at least a portion of the hostname is visible.
    > **FIXED**: T079 — Added `min-width: 120px` on host input, error message now truncates with ellipsis (full text on hover).
