import { z } from 'zod';

const envSchema = z.object({
  PORT: z.coerce.number().default(8000),
  HOST: z.string().default('0.0.0.0'),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),

  DATABASE_URL: z.string(),
  REDIS_URL: z.string().default('redis://localhost:6379'),

  JWT_SECRET: z.string().min(16),
  JWT_EXPIRES_IN_HOURS: z.coerce.number().default(24),

  CORS_ORIGINS: z.string().default('http://localhost:5173,http://localhost:3000'),

  AGENT_SCRIPT_PATH: z.string().default('../agent/coordinator_main.py'),
  PYTHON_PATH: z.string().default('python'),
  AGENT_MODE: z.enum(['direct', 'coordinator']).default('direct'),

  LLM_PROVIDER: z.string().default('dashscope'),
  LLM_MODEL_NAME: z.string().default('qwen3-max-preview'),
  LLM_API_KEY: z.string().default(''),

  STORAGE_ROOT: z.string().default('../storage'),
});

function loadConfig() {
  const parsed = envSchema.safeParse(process.env);

  if (!parsed.success) {
    const formatted = parsed.error.format();
    throw new Error(`Invalid environment variables:\n${JSON.stringify(formatted, null, 2)}`);
  }

  const env = parsed.data;

  return {
    port: env.PORT,
    host: env.HOST,
    nodeEnv: env.NODE_ENV,
    isDev: env.NODE_ENV === 'development',
    isProd: env.NODE_ENV === 'production',

    database: {
      url: env.DATABASE_URL,
    },

    redis: {
      url: env.REDIS_URL,
    },

    jwt: {
      secret: env.JWT_SECRET,
      expiresInHours: env.JWT_EXPIRES_IN_HOURS,
    },

    cors: {
      origins: env.CORS_ORIGINS.split(',').map((s) => s.trim()),
    },

    agent: {
      scriptPath: env.AGENT_SCRIPT_PATH,
      pythonPath: env.PYTHON_PATH,
      mode: env.AGENT_MODE,
    },

    llm: {
      provider: env.LLM_PROVIDER,
      modelName: env.LLM_MODEL_NAME,
      apiKey: env.LLM_API_KEY,
    },

    storage: {
      root: env.STORAGE_ROOT,
    },
  } as const;
}

export type AppConfig = ReturnType<typeof loadConfig>;

let _config: AppConfig | null = null;

export function getConfig(): AppConfig {
  if (!_config) {
    _config = loadConfig();
  }
  return _config;
}
