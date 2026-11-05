targetScope = 'subscription'

@minLength(1)
@maxLength(32)
param environmentName string
param location string

@secure()
@description('Inject through a secure deployment parameter. Never commit a token.')
param copilotGithubToken string

@description('The azd deploy step replaces the bootstrap image with the ACR build.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

resource resourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
    project: 'gamjaba'
  }
}

module app './resources.bicep' = {
  name: 'gamjaba-resources'
  scope: resourceGroup
  params: {
    location: location
    environmentName: environmentName
    copilotGithubToken: copilotGithubToken
    containerImage: containerImage
  }
}

output AZURE_RESOURCE_GROUP string = resourceGroup.name
output AZURE_LOCATION string = location
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryEndpoint
output AZURE_CONTAINER_REGISTRY_NAME string = app.outputs.registryName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = app.outputs.environmentId
output AZURE_CONTAINER_APP_NAME string = app.outputs.appName
output SERVICE_API_RESOURCE_NAME string = app.outputs.appName
output SERVICE_API_URI string = app.outputs.appUrl
