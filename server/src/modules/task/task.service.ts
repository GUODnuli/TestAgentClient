import { getPrisma } from '../../config/database.js';
import { getLogger } from '../../config/logger.js';
import { NotFoundError } from '../../common/errors.js';
import { formatTask } from '../../common/utils.js';
import type { TaskStatus, Prisma } from '@prisma/client';

export async function createTask(
  userId: string,
  taskType: string,
  parameters: Record<string, unknown>
) {
  const prisma = getPrisma();
  const logger = getLogger();

  const task = await prisma.task.create({
    data: {
      userId,
      taskType,
      parameters: parameters as Prisma.InputJsonValue,
    },
  });

  logger.info({ taskId: task.id, userId, taskType }, 'Task created');
  return formatTask(task);
}

export async function getTask(taskId: string) {
  const prisma = getPrisma();

  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) {
    throw new NotFoundError('任务');
  }

  return formatTask(task);
}

export async function listTasks(
  userId: string,
  options: {
    status?: string;
    taskType?: string;
    limit?: number;
    offset?: number;
    orderBy?: string;
    orderDir?: string;
  }
) {
  const prisma = getPrisma();

  const where: Prisma.TaskWhereInput = { userId };

  if (options.status) {
    where.status = options.status as TaskStatus;
  }
  if (options.taskType) {
    where.taskType = options.taskType;
  }

  const orderField = options.orderBy ?? 'createdAt';
  const orderMap: Record<string, string> = {
    created_at: 'createdAt',
    updated_at: 'updatedAt',
    status: 'status',
  };
  const prismaOrderField = orderMap[orderField] ?? 'createdAt';

  const tasks = await prisma.task.findMany({
    where,
    orderBy: { [prismaOrderField]: options.orderDir === 'asc' ? 'asc' : 'desc' },
    take: options.limit ?? 100,
    skip: options.offset ?? 0,
  });

  return tasks.map(formatTask);
}

export async function updateTaskStatus(
  taskId: string,
  status: string,
  errorMessage?: string | null
) {
  const prisma = getPrisma();
  const logger = getLogger();

  const data: Prisma.TaskUpdateInput = {
    status: status as TaskStatus,
    errorMessage: errorMessage ?? null,
  };

  if (status === 'RUNNING') {
    data.startedAt = new Date();
  }
  if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(status)) {
    data.completedAt = new Date();
  }

  const task = await prisma.task.update({
    where: { id: taskId },
    data,
  });

  logger.info({ taskId, status }, 'Task status updated');
  return formatTask(task);
}

export async function deleteTask(taskId: string) {
  const prisma = getPrisma();

  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) {
    throw new NotFoundError('任务');
  }

  await prisma.task.delete({ where: { id: taskId } });
  return { message: '任务已删除' };
}

export async function getTaskStatistics(userId: string) {
  const prisma = getPrisma();

  const total = await prisma.task.count({ where: { userId } });

  const statusCounts = await prisma.task.groupBy({
    by: ['status'],
    where: { userId },
    _count: true,
  });

  const typeCounts = await prisma.task.groupBy({
    by: ['taskType'],
    where: { userId },
    _count: true,
  });

  return {
    total_count: total,
    status_counts: Object.fromEntries(statusCounts.map((s) => [s.status, s._count])),
    type_counts: Object.fromEntries(typeCounts.map((t) => [t.taskType, t._count])),
  };
}
