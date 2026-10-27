## FastAPI

The Python rules apply. These add what a FastAPI reviewer checks in a small service.

- **API-VALID** (major): input is validated with `if` checks inside a handler where a Pydantic model field or an `Annotated`/`Query`/`Path` constraint would do it and return the 422 automatically.
- **API-MODEL** (major): the response is an untyped `dict` where a response model belongs, request and response models are one class when their fields differ, or internal state leaks into a response.
- **API-STATUS** (major): a wrong status code for the action (create is 201, delete with no body is 204, missing is 404), or an error raised without `HTTPException` and a clear `detail`.
- **API-ASYNC** (major): an `async def` handler that calls blocking code, or that awaits nothing where a plain `def` handler would run in the thread pool.
- **API-DEPS** (minor): the same lookup or check repeated in several handlers where a dependency or one helper belongs, or a handler that holds logic unrelated to HTTP.
- **API-STATE** (major): state shared between app instances through module globals when each call to `solution()` must return an independent app.
