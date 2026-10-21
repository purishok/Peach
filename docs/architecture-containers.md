# Peach container diagram (C4 level 2)

```mermaid
flowchart LR
    Person[Person] -->|paste text / check suggestion| Browser[Browser: Next.js]
    Browser -->|parse: Cognito token + text| Parser[Agenda parser: Lambda outside VPC]
    Parser -->|Converse tool call| Bedrock[Amazon Bedrock: Claude Sonnet 4.5]
    Bedrock -->|structured suggestion| Parser
    Parser -->|validated JSON| Browser
    Browser -->|save: final agenda + suggestion| API[Main API: FastAPI inside VPC]
    API -->|validated write| DB[(Aurora PostgreSQL)]
    Cognito[Amazon Cognito] -->|ID token / signing keys| Browser
    Cognito -->|JWKS| Parser
    Cognito -->|JWKS configured at deploy| API
```

The parser has no database access. Its public function URL validates Cognito
before calling the paid model. The existing API enforces meeting ownership and
stores both the suggestion and the checked result. In this deployment the
parser and Bedrock billing are in AWS account `985040259102`, while the site,
Cognito pool, main API and database remain in account `505464394565`.
