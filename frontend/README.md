# Console frontend

React source for the Segma Realtime Console. See the [root README](../README.md)
for installation, building, and serving with FastAPI.

- `npm start`: development server on port 3000. Set
  `REACT_APP_WS_URL=ws://localhost:8000/ws` to connect to the backend.
- `npm run build`: create `build/`, served by the root FastAPI application.
- `npm test`: run frontend tests.
