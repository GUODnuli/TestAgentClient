/**
 * Migration script: SQLite → PostgreSQL
 *
 * Reads data from the existing SQLite database and writes it to PostgreSQL via Prisma.
 *
 * Usage: npx tsx scripts/migrate-sqlite-to-pg.ts
 *
 * Prerequisites:
 *   - PostgreSQL running with schema migrated (npx prisma migrate dev)
 *   - SQLite database at ../storage/tasks.db
 */
import 'dotenv/config';
import Database from 'better-sqlite3';
import { PrismaClient, type UserRole, type UserStatus, type TaskStatus } from '@prisma/client';
import path from 'path';

const SQLITE_PATH = path.resolve('../storage/tasks.db');

async function main() {
  console.log('=== SQLite → PostgreSQL Migration ===');
  console.log(`SQLite path: ${SQLITE_PATH}`);

  const sqlite = new Database(SQLITE_PATH, { readonly: true });
  const prisma = new PrismaClient();

  try {
    await prisma.$connect();
    console.log('PostgreSQL connected');

    // 1. Migrate Users
    console.log('\n--- Migrating Users ---');
    const users = sqlite.prepare('SELECT * FROM users').all() as Array<Record<string, unknown>>;
    console.log(`Found ${users.length} users`);

    for (const user of users) {
      try {
        await prisma.user.create({
          data: {
            id: user.user_id as string,
            username: user.username as string,
            email: (user.email as string) || null,
            passwordHash: user.password_hash as string,
            displayName: (user.display_name as string) || null,
            role: ((user.role as string) || 'user').toUpperCase() as UserRole,
            status: ((user.status as string) || 'active').toUpperCase() as UserStatus,
            createdAt: new Date(user.created_at as string),
            updatedAt: new Date(user.updated_at as string),
            lastLoginAt: user.last_login_at ? new Date(user.last_login_at as string) : null,
          },
        });
      } catch (err) {
        console.warn(`  Skip user ${user.username}: ${err}`);
      }
    }
    console.log(`Users migrated: ${users.length}`);

    // 2. Migrate Conversations
    console.log('\n--- Migrating Conversations ---');
    const conversations = sqlite.prepare('SELECT * FROM conversations').all() as Array<Record<string, unknown>>;
    console.log(`Found ${conversations.length} conversations`);

    for (const conv of conversations) {
      try {
        await prisma.conversation.create({
          data: {
            id: conv.conversation_id as string,
            userId: conv.user_id as string,
            title: conv.title as string,
            createdAt: new Date(conv.created_at as string),
            updatedAt: new Date(conv.updated_at as string),
          },
        });
      } catch (err) {
        console.warn(`  Skip conversation ${conv.conversation_id}: ${err}`);
      }
    }
    console.log(`Conversations migrated: ${conversations.length}`);

    // 3. Migrate Messages
    console.log('\n--- Migrating Messages ---');
    const messages = sqlite.prepare('SELECT * FROM messages').all() as Array<Record<string, unknown>>;
    console.log(`Found ${messages.length} messages`);

    // Batch insert for performance
    const BATCH_SIZE = 500;
    for (let i = 0; i < messages.length; i += BATCH_SIZE) {
      const batch = messages.slice(i, i + BATCH_SIZE);
      try {
        await prisma.message.createMany({
          data: batch.map((msg) => ({
            id: msg.message_id as string,
            conversationId: msg.conversation_id as string,
            role: msg.role as string,
            content: msg.content as string,
            createdAt: new Date(msg.created_at as string),
          })),
          skipDuplicates: true,
        });
      } catch (err) {
        console.warn(`  Batch error at ${i}: ${err}`);
        // Fall back to individual inserts
        for (const msg of batch) {
          try {
            await prisma.message.create({
              data: {
                id: msg.message_id as string,
                conversationId: msg.conversation_id as string,
                role: msg.role as string,
                content: msg.content as string,
                createdAt: new Date(msg.created_at as string),
              },
            });
          } catch {
            // Skip individual failures
          }
        }
      }
      console.log(`  Messages ${i + 1}-${Math.min(i + BATCH_SIZE, messages.length)} processed`);
    }
    console.log(`Messages migrated: ${messages.length}`);

    // 4. Migrate Tasks
    console.log('\n--- Migrating Tasks ---');
    const tasks = sqlite.prepare('SELECT * FROM tasks').all() as Array<Record<string, unknown>>;
    console.log(`Found ${tasks.length} tasks`);

    for (const task of tasks) {
      try {
        await prisma.task.create({
          data: {
            id: task.task_id as string,
            userId: (task.user_id as string) || null,
            taskType: task.task_type as string,
            status: (task.status as string) as TaskStatus,
            parameters: task.parameters ? JSON.parse(task.parameters as string) : null,
            result: task.result ? JSON.parse(task.result as string) : null,
            checkpoint: task.checkpoint ? JSON.parse(task.checkpoint as string) : null,
            errorMessage: (task.error_message as string) || null,
            createdAt: new Date(task.created_at as string),
            updatedAt: new Date(task.updated_at as string),
            startedAt: task.started_at ? new Date(task.started_at as string) : null,
            completedAt: task.completed_at ? new Date(task.completed_at as string) : null,
          },
        });
      } catch (err) {
        console.warn(`  Skip task ${task.task_id}: ${err}`);
      }
    }
    console.log(`Tasks migrated: ${tasks.length}`);

    // 5. Verification
    console.log('\n--- Verification ---');
    const pgUsers = await prisma.user.count();
    const pgConversations = await prisma.conversation.count();
    const pgMessages = await prisma.message.count();
    const pgTasks = await prisma.task.count();

    console.log(`PostgreSQL counts: users=${pgUsers}, conversations=${pgConversations}, messages=${pgMessages}, tasks=${pgTasks}`);
    console.log(`SQLite counts:    users=${users.length}, conversations=${conversations.length}, messages=${messages.length}, tasks=${tasks.length}`);

    const allMatch =
      pgUsers === users.length &&
      pgConversations === conversations.length &&
      pgMessages === messages.length &&
      pgTasks === tasks.length;

    if (allMatch) {
      console.log('\nMigration SUCCESSFUL - all counts match!');
    } else {
      console.warn('\nMigration completed with some skipped records. Check warnings above.');
    }
  } finally {
    sqlite.close();
    await prisma.$disconnect();
  }
}

main().catch((err) => {
  console.error('Migration failed:', err);
  process.exit(1);
});
