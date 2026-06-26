#!/usr/bin/env node
/**
 * local-gateway — Desktop LLM gateway with multi-provider failover
 *
 * Node.js implementation. Pure built-in modules (http, https).
 * Usage: node local-gateway.js --providers deepseek,kimi
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

// ── Built-in provider registry ────────────────────────────────────────
const BUILTIN_PROVIDERS = {
  deepseek:   { base_url: 'https://api.deepseek.com/v1',             env_key: 'DEEPSEEK_API_KEY',  default_model: 'deepseek-chat' },
  kimi:       { base_url: 'https://api.moonshot.cn/v1',              env_key: 'KIMI_API_KEY',      default_model: 'moonshot-v1-128k' },
  openai:     { base_url: 'https://api.openai.com/v1',               env_key: 'OPENAI_API_KEY',    default_model: 'gpt-4o' },
  openrouter: { base_url: 'https://openrouter.ai/api/v1',            env_key: 'OPENROUTER_API_KEY',default_model: 'openai/gpt-4o' },
  anthropic:  { base_url: 'https://api.anthropic.com/v1',            env_key: 'ANTHROPIC_API_KEY', default_model: 'claude-sonnet-4-20250514' },
  groq:       { base_url: 'https://api.groq.com/openai/v1',          env_key: 'GROQ_API_KEY',      default_model: 'llama-3.3-70b-versatile' },
  together:   { base_url: 'https://api.together.xyz/v1',             env_key: 'TOGETHER_API_KEY',  default_model: 'meta-llama/Llama-3.3-70B-Instruct-Turbo' },
  mistral:    { base_url: 'https://api.mistral.ai/v1',               env_key: 'MISTRAL_API_KEY',   default_model: 'mistral-large-latest' },
  google:     { base_url: 'https://generativelanguage.googleapis.com/v1beta/openai', env_key: 'GOOGLE_API_KEY', default_model: 'gemini-2.0-flash' },
};

// ── Cross-provider model name mapping ─────────────────────────────────
const MODEL_MAP = {
  'deepseek-chat|deepseek|kimi':       'moonshot-v1-128k',
  'deepseek-chat|deepseek|openai':     'gpt-4o',
  'deepseek-chat|deepseek|openrouter': 'deepseek/deepseek-chat',
  'deepseek-chat|deepseek|groq':       'llama-3.3-70b-versatile',
  'gpt-4o|openai|deepseek':            'deepseek-chat',
  'gpt-4o|openai|kimi':               'moonshot-v1-128k',
  'gpt-4o|openai|openrouter':          'openai/gpt-4o',
  'claude-sonnet-4-20250514|anthropic|openai':   'gpt-4o',
  'claude-sonnet-4-20250514|anthropic|deepseek': 'deepseek-chat',
};

function resolveModel(model, fromProvider, toProvider) {
  const key = `${model}|${fromProvider}|${toProvider}`;
  const mapped = MODEL_MAP[key];
  if (mapped) return mapped;
  console.warn(`[local-gateway] No model mapping for '${model}' ${fromProvider} -> ${toProvider}, passing through`);
  return model;
}

// ── Provider loading ──────────────────────────────────────────────────
function loadProviders(names, apiKeys = {}) {
  return names.map(name => {
    let spec = BUILTIN_PROVIDERS[name];
    if (!spec) {
      console.warn(`[local-gateway] Unknown provider '${name}', using generic`);
      spec = { base_url: `https://api.${name}.com/v1`, env_key: `${name.toUpperCase()}_API_KEY`, default_model: `${name}-default` };
    }
    let key = apiKeys[name] || process.env[spec.env_key] || process.env[`${name.toUpperCase()}_API_KEY`];
    if (!key) throw new Error(`API key for '${name}' not found. Set ${spec.env_key} env var.`);
    return { name, base_url: spec.base_url, api_key: key, default_model: spec.default_model };
  });
}

// ── HTTP client helper (pure Node.js, no dependencies) ────────────────
function upstreamRequest(urlStr, data, apiKey, modelName, isStream) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    const body = JSON.stringify({ ...JSON.parse(data), model: modelName, stream: isStream });
    const opts = {
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname + url.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'User-Agent': 'local-gateway/1.0.0',
        'Content-Length': Buffer.byteLength(body),
      },
    };

    const req = https.request(opts, (res) => {
      resolve(res);
    });
    req.on('error', reject);
    req.setTimeout(120000, () => { req.destroy(new Error('timeout')); });
    req.write(body);
    req.end();
  });
}

// ── SSE streaming helper ──────────────────────────────────────────────
function pipeStream(upstreamRes, clientRes) {
  upstreamRes.on('data', chunk => {
    clientRes.write(chunk);
  });
  upstreamRes.on('end', () => clientRes.end());
  upstreamRes.on('error', () => clientRes.end());
}

// ── Parse CLI args ────────────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { providers: [], port: 18790, host: '127.0.0.1', apiKeys: {} };
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--providers': case '-p':
        opts.providers = (args[++i] || '').split(',').map(s => s.trim()).filter(Boolean);
        break;
      case '--port':
        opts.port = parseInt(args[++i] || '18790', 10);
        break;
      case '--host':
        opts.host = args[++i] || '127.0.0.1';
        break;
      case '--api-key':
        const kv = args[++i] || '';
        const eq = kv.indexOf('=');
        if (eq > 0) opts.apiKeys[kv.slice(0, eq)] = kv.slice(eq + 1);
        break;
      case '--list-providers':
        console.log('Built-in providers:\n');
        Object.entries(BUILTIN_PROVIDERS).forEach(([k, v]) => {
          console.log(`  ${k.padEnd(15)} ${v.base_url}`);
          console.log(`                  env: ${v.env_key}`);
          console.log(`                  default model: ${v.default_model}\n`);
        });
        process.exit(0);
      case '--list-models':
        console.log('# Cross-Provider Model Name Mapping\n');
        const seen = new Set();
        Object.entries(MODEL_MAP).sort().forEach(([key, mapped]) => {
          const [model, src, dst] = key.split('|');
          const sk = `${model}|${src}`;
          if (!seen.has(sk)) { seen.add(sk); console.log(`\n${model}  (${src})`); }
          console.log(`  => ${String(mapped).padEnd(40)} (${dst})`);
        });
        process.exit(0);
      case '--version':
        console.log('local-gateway 1.0.0');
        process.exit(0);
    }
  }
  return opts;
}

// ── Main: HTTP Server ─────────────────────────────────────────────────
function main() {
  const opts = parseArgs();

  if (!opts.providers.length) {
    console.error('Usage: local-gateway --providers deepseek,kimi [--port 18790] [--host 127.0.0.1]');
    console.error('       local-gateway --list-providers');
    console.error('       local-gateway --list-models');
    process.exit(1);
  }

  const providers = loadProviders(opts.providers, opts.apiKeys);
  const providerOrder = opts.providers;

  const server = http.createServer((req, res) => {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS, GET');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

    if (req.method === 'OPTIONS') {
      res.writeHead(204);
      res.end();
      return;
    }

    // GET /health
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', providers: providerOrder }));
      return;
    }

    // POST /v1/chat/completions
    if (req.method === 'POST' && req.url.includes('/chat/completions')) {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', async () => {
        let parsed;
        try { parsed = JSON.parse(body); } catch (e) {
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: { message: `Invalid JSON: ${e.message}` } }));
          return;
        }

        const isStream = parsed.stream === true;
        const originalModel = parsed.model || '';
        let lastError = null;

        for (let idx = 0; idx < providerOrder.length; idx++) {
          const pName = providerOrder[idx];
          const p = providers.find(pr => pr.name === pName);
          if (!p) continue;

          const model = idx === 0
            ? (originalModel || p.default_model)
            : resolveModel(originalModel || p.default_model, providerOrder[0], pName);

          const url = `${p.base_url.replace(/\/+$/, '')}/chat/completions`;

          try {
            const upstreamRes = await upstreamRequest(url, body, p.api_key, model, isStream);

            if (upstreamRes.statusCode !== 200) {
              let errData = '';
              await new Promise(r => { upstreamRes.on('data', d => errData += d); upstreamRes.on('end', r); });
              console.warn(`[local-gateway] FAIL ${pName} — HTTP ${upstreamRes.statusCode}: ${errData.slice(0, 200)}`);
              lastError = { provider: pName, status: upstreamRes.statusCode };
              continue;
            }

            // Connected — forward response
            console.log(`[local-gateway] 200 ${pName} (${isStream ? 'stream' : 'sync'})`);

            if (isStream) {
              res.writeHead(200, {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'close',
              });
              pipeStream(upstreamRes, res);
            } else {
              let respData = '';
              await new Promise(r => { upstreamRes.on('data', d => respData += d); upstreamRes.on('end', r); });
              res.writeHead(200, {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(respData),
              });
              res.end(respData);
            }
            return;

          } catch (e) {
            console.warn(`[local-gateway] FAIL ${pName} — ${e.message}`);
            lastError = { provider: pName, status: 0, detail: e.message };
          }
        }

        // All failed
        console.error(`[local-gateway] ALL PROVIDERS FAILED`);
        res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          error: { message: `All providers failed. Last: ${lastError?.provider || 'none'}`, type: 'upstream_error' }
        }));
      });
      return;
    }

    // 404
    res.writeHead(404);
    res.end('not found');
  });

  server.listen(opts.port, opts.host, () => {
    console.log('='.repeat(55));
    console.log('  LocalGateway (Node.js)');
    console.log(`  listening on http://${opts.host}:${opts.port}`);
    console.log(`  providers: ${providerOrder.join(', ')}`);
    console.log('  streaming: supported (SSE passthrough)');
    console.log('='.repeat(55));
  });
}

// ── Entry ─────────────────────────────────────────────────────────────
if (require.main === module) main();
module.exports = { BUILTIN_PROVIDERS, MODEL_MAP, loadProviders, resolveModel };
