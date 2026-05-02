// infra/main.bicep
// MemorAI — Azure infrastructure deployment
// Deploy: az deployment group create --resource-group memorai-rg --template-file infra/main.bicep --parameters @infra/parameters.json

@description('Environment name (dev, staging, prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Unique suffix to avoid naming conflicts')
param suffix string = uniqueString(resourceGroup().id)

var prefix = 'memorai-${environment}'

// ── Azure OpenAI ────────────────────────────────────────────────────────────

resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${prefix}-openai-${suffix}'
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: '${prefix}-openai-${suffix}'
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAI
  name: 'gpt-4o'
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
  }
  sku: {
    name: 'Standard'
    capacity: 30
  }
}

// ── Azure AI Speech ─────────────────────────────────────────────────────────

resource speech 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${prefix}-speech-${suffix}'
  location: location
  kind: 'SpeechServices'
  sku: { name: 'S0' }
  properties: { publicNetworkAccess: 'Enabled' }
}

// ── Azure AI Vision ─────────────────────────────────────────────────────────

resource vision 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${prefix}-vision-${suffix}'
  location: location
  kind: 'ComputerVision'
  sku: { name: 'S1' }
  properties: { publicNetworkAccess: 'Enabled' }
}

// ── Azure AI Translator ─────────────────────────────────────────────────────

resource translator 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: '${prefix}-translator-${suffix}'
  location: location
  kind: 'TextTranslation'
  sku: { name: 'S1' }
  properties: { publicNetworkAccess: 'Enabled' }
}

// ── Azure Cosmos DB ─────────────────────────────────────────────────────────

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: '${prefix}-cosmos-${suffix}'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [{ locationName: location, failoverPriority: 0 }]
  }
}

resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: 'memorai'
  properties: { resource: { id: 'memorai' } }
}

resource storiesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'stories'
  properties: {
    resource: {
      id: 'stories'
      partitionKey: { paths: ['/senior_id'], kind: 'Hash' }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
      }
    }
    options: { autoscaleSettings: { maxThroughput: 4000 } }
  }
}

resource profilesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'profiles'
  properties: {
    resource: {
      id: 'profiles'
      partitionKey: { paths: ['/senior_id'], kind: 'Hash' }
    }
    options: { autoscaleSettings: { maxThroughput: 1000 } }
  }
}

// ── Azure AI Search ─────────────────────────────────────────────────────────

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${prefix}-search-${suffix}'
  location: location
  sku: { name: 'standard' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    semanticSearch: 'standard'
  }
}

// ── Azure Storage (photos + function queues) ────────────────────────────────

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'memorai${suffix}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
}

// ── Azure Functions ─────────────────────────────────────────────────────────

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${prefix}-plan-${suffix}'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
  kind: 'functionapp'
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${prefix}-functions-${suffix}'
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      pythonVersion: '3.11'
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value}' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAI.properties.endpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: 'gpt-4o' }
        { name: 'COSMOS_ENDPOINT', value: cosmosAccount.properties.documentEndpoint }
        { name: 'SEARCH_ENDPOINT', value: 'https://${search.name}.search.windows.net' }
      ]
    }
  }
}

// ── Azure App Service (family portal) ──────────────────────────────────────

resource portalPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${prefix}-portal-plan-${suffix}'
  location: location
  sku: { name: 'B2' }
  kind: 'linux'
  properties: { reserved: true }
}

resource portalApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${prefix}-portal-${suffix}'
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: portalPlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'uvicorn app.main:app --host 0.0.0.0 --port 8000'
    }
  }
}

// ── Outputs ─────────────────────────────────────────────────────────────────

output openAIEndpoint string = openAI.properties.endpoint
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output portalUrl string = 'https://${portalApp.properties.defaultHostName}'
