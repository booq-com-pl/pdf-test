curl -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/booq-com-pl/pdf-test/actions/workflows/document-update.yaml/dispatches \
  -d '{
    "ref":"main",
    "inputs": {
    "payload": "{\"lastName\":\"Kowalski\",\"firstName\":\"Jan\",\"birthDate\":\"1985-03-15\",\"pesel\":\"85031512345\",\"employerName\":\"ABC Corporation\"}"
    }
  }'