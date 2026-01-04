curl -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer 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" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/booq-com-pl/pdf-test/actions/workflows/document-update.yaml/dispatches \
  -d '{
    "ref":"main",
    "inputs": {
      "payload": "{\"task\":\"reindex\",\"env\":\"prod\"}"
    }
  }'