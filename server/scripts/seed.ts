/**
 * Seed script: Create initial admin user
 *
 * Usage: npx tsx scripts/seed.ts
 */
import 'dotenv/config';
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

async function main() {
  const prisma = new PrismaClient();

  try {
    await prisma.$connect();
    console.log('Connected to PostgreSQL');

    // Check if admin exists
    const existing = await prisma.user.findUnique({ where: { username: 'admin' } });
    if (existing) {
      console.log('Admin user already exists, skipping seed');
      return;
    }

    const passwordHash = await bcrypt.hash('admin123', 10);

    const admin = await prisma.user.create({
      data: {
        username: 'admin',
        passwordHash,
        displayName: '管理员',
        role: 'ADMIN',
        status: 'ACTIVE',
      },
    });

    console.log(`Admin user created: ${admin.id}`);
    console.log('Username: admin');
    console.log('Password: admin123');
    console.log('\nPlease change the password after first login!');
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
