import pino from 'pino';

let logger: pino.Logger | null = null;

export function getLogger(): pino.Logger {
  if (!logger) {
    const isDev = process.env.NODE_ENV !== 'production';

    logger = pino({
      level: isDev ? 'debug' : 'info',
      transport: isDev
        ? {
            target: 'pino-pretty',
            options: {
              colorize: true,
              translateTime: 'SYS:yyyy-mm-dd HH:MM:ss.l',
              ignore: 'pid,hostname',
            },
          }
        : undefined,
    });
  }
  return logger;
}
