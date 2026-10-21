# Peach container diagram (C4 level 2)

```mermaid
flowchart LR
    Person[Person] -->|paste text / check suggestion| Browser[Browser: Next.js]
    Browser -->|parse: Cognito token + text| Parser[Agenda parser: Lambda outside VPC]
    Parser -->|Messages API tool call| Bedrock[Amazon Bedrock: Claude]
    Bedrock -->|structured suggestion| Parser
    Parser -->|validated JSON| Browser
    Browser -->|save: final agenda + suggestion| API[Main API: FastAPI inside VPC]
    API -->|validated write| DB[(PostgreSQL)]
    Cognito[Amazon Cognito] -->|ID token / signing keys| Browser
    Cognito -->|JWKS| Parser
    Cognito -->|JWKS configured at deploy| API
```

The parser has no database access. Its public function URL validates Cognito
before calling the paid model. The existing API enforces meeting ownership and
stores both the suggestion and the checked result.
