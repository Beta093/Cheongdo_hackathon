param location string
param environmentName string
@secure()
param copilotGithubToken string
@secure()
param weatherApiKey string = ''
@allowed(['memory', 'cosmos'])
param storageMode string = 'memory'
param containerImage string

var suffix = uniqueString(resourceGroup().id)
var databaseName = 'gamjaba'
var containerName = 'state'
// The bootstrap image listens on 80; the actual Dockerfile exposes 8000.
var targetPort = containerImage == 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' ? 80 : 8000
var tags = {
  'azd-env-name': environmentName
  project: 'gamjaba'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${suffix}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: 1 }
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'acrgamjaba${suffix}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${suffix}'
  location: location
  tags: tags
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'pull')
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'kv-gam-${suffix}'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource vaultRead 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, 'secrets-read')
  scope: vault
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource modelSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'assistant-token'
  properties: { value: copilotGithubToken }
}

resource weatherSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(weatherApiKey)) {
  parent: vault
  name: 'weather-key'
  properties: { value: weatherApiKey }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${suffix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
  }
}

resource telemetrySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'telemetry-connection'
  properties: { value: insights.properties.ConnectionString }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-${suffix}'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [{ name: 'EnableServerless' }]
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{
      locationName: location
      failoverPriority: 0
      isZoneRedundant: false
    }]
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: databaseName
  properties: { resource: { id: databaseName } }
}

resource stateContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: ['/farmId']
        kind: 'Hash'
        version: 2
      }
      defaultTtl: -1
      indexingPolicy: {
        indexingMode: 'none'
        automatic: false
      }
    }
  }
}

resource cosmosAccess 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, identity.id, 'data-contributor')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: identity.properties.principalId
    scope: '${cosmos.id}/dbs/${databaseName}/colls/${containerName}'
  }
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${suffix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-gamjaba-${suffix}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  dependsOn: [
    vaultRead
    registryPull
    cosmosAccess
    stateContainer
    weatherSecret
  ]
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
      }
      secrets: concat([
        {
          name: 'copilot-token'
          keyVaultUrl: modelSecret.properties.secretUri
          identity: identity.id
        }
        {
          name: 'telemetry-connection'
          keyVaultUrl: telemetrySecret.properties.secretUri
          identity: identity.id
        }
      ], empty(weatherApiKey) ? [] : [{
        name: 'weather-key'
        keyVaultUrl: '${vault.properties.vaultUri}secrets/weather-key'
        identity: identity.id
      }])
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          env: concat([
            {
              name: 'COPILOT_GITHUB_TOKEN'
              secretRef: 'copilot-token'
            }
            {
              name: 'GAMJABA_MODEL'
              value: 'copilot'
            }
            {
              name: 'GAMJABA_STORE'
              value: storageMode
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmos.properties.documentEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: databaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: containerName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identity.properties.clientId
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'telemetry-connection'
            }
          ], empty(weatherApiKey) ? [] : [{
            name: 'WEATHER_API_KEY'
            secretRef: 'weather-key'
          }])
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          // TCP probes avoid fabricating a session UUID or weakening /api/health.
          probes: [
            {
              type: 'Startup'
              tcpSocket: { port: targetPort }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              tcpSocket: { port: targetPort }
              periodSeconds: 30
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              tcpSocket: { port: targetPort }
              periodSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      scale: {
        // Memory needs one replica. Cosmos preserves data across restarts, but the
        // rate limiter and model concurrency budget remain process-local in P1.
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output registryEndpoint string = registry.properties.loginServer
output registryName string = registry.name
output environmentId string = environment.id
output appName string = containerApp.name
output appUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
