# Store explicit ownership on every user resource

Every user-owned Cognion table stores a non-null User identifier, including child and association records whose ownership could otherwise be inferred through a parent. The backend derives that identifier from the authenticated User and verified parent resources rather than client input; the deliberate redundancy enables uniform ownership filtering and reduces the chance that a missing join exposes another User Space.
