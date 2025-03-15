const { datasets } = require('@huggingface/hub');

// Import Python functions
const { spawn } = require('child_process');
const path = require('path');

async function runPythonFunction(scriptPath, data) {
  return new Promise((resolve, reject) => {
    const process = spawn('python', [scriptPath, JSON.stringify(data)]);
    let result = '';
    let error = '';

    process.stdout.on('data', (data) => {
      result += data.toString();
    });

    process.stderr.on('data', (data) => {
      error += data.toString();
    });

    process.on('close', (code) => {
      if (code !== 0) {
        reject(new Error(error));
      } else {
        resolve(JSON.parse(result));
      }
    });
  });
}

exports.handler = async function(event, context) {
  try {
    const action = event.queryStringParameters?.action || 'get-tenders';
    const params = { ...event.queryStringParameters };
    delete params.action;

    switch (action) {
      case 'get-tenders':
        const dataset = params.dataset || 'open-tenders';
        const datasetMap = {
          'open-tenders': 'Olive254/OpenTenderPPIPFormat',
          'awarded-contracts': 'Kenya published_contracts.csv',
          'procurement-plans': 'Olive254/OGA_KE_ProcurementPlans'
        };
        
        const data = await datasets.load(datasetMap[dataset], {
          split: 'train',
          limit: parseInt(params.limit) || 100,
          offset: parseInt(params.offset) || 0
        });
        
        return {
          statusCode: 200,
          body: JSON.stringify({ success: true, data })
        };

      case 'predict-price':
        const priceResult = await runPythonFunction(
          path.join(__dirname, 'price-analysis.py'),
          JSON.parse(event.body)
        );
        return {
          statusCode: 200,
          body: JSON.stringify(priceResult)
        };

      case 'match-suppliers':
        const suppliersResult = await runPythonFunction(
          path.join(__dirname, 'supplier-matching.py'),
          JSON.parse(event.body)
        );
        return {
          statusCode: 200,
          body: JSON.stringify(suppliersResult)
        };

      case 'scrape-tenders':
        const scrapeResult = await runPythonFunction(
          path.join(__dirname, 'scraper.py'),
          params
        );
        return {
          statusCode: 200,
          body: JSON.stringify(scrapeResult)
        };

      default:
        return {
          statusCode: 400,
          body: JSON.stringify({ 
            success: false, 
            error: 'Invalid action specified' 
          })
        };
    }
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({
        success: false,
        error: error.message
      })
    };
  }
};
