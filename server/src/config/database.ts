import { PrismaClient } from '@prisma/client';
import { getConfig } from './index.js';

let prisma: PrismaClient | null = null;

export function getPrisma(): PrismaClient {
  if (!prisma) {
    prisma = new PrismaClient({
      datasourceUrl: getConfig().database.url,
      log: getConfig().isDev ? ['warn', 'error'] : ['error'],
    });
  }
  return prisma;
}

export async function disconnectPrisma(): Promise<void> {
  if (prisma) {
    await prisma.$disconnect();
    prisma = null;
  }
}
