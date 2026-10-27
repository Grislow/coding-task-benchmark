## Express

The JavaScript rules apply. These add what an Express reviewer checks in a small service.

- **EXP-VALID** (major): input is used without validation, or validation is scattered `if` checks repeated across handlers where one small validator or middleware belongs; invalid input must answer 400 or 422 with a clear message, never a 500.
- **EXP-SHAPE** (major): a response leaks internal state or the stored object itself, returns a different shape for the same resource in different routes, or sends plain text where the API is JSON.
- **EXP-STATUS** (major): a wrong status code for the action (create is 201, delete with no body is 204, missing is 404), or an error that falls through to Express's default 500 handler.
- **EXP-ASYNC** (major): blocking work in a handler, an async handler whose rejection is not handled, or `async` on a handler that awaits nothing.
- **EXP-MIDDLE** (minor): the same lookup or check repeated in several handlers where a middleware, `router.param` or one helper belongs, or a handler that holds logic unrelated to HTTP.
- **EXP-STATE** (major): state shared between app instances through module-level variables when each call to `solution()` must return an independent app.
