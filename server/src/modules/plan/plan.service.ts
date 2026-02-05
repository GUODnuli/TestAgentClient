import { Prisma } from '@prisma/client';
import { getPrisma } from '../../config/database.js';
import { getLogger } from '../../config/logger.js';

export interface CoordinatorPlanData {
  objective: string;
  plan: Record<string, unknown>;
  activePhase?: number | null;
  completedPhases?: number[];
  phaseOutputs?: Record<string, unknown> | null;
  status?: string;
}

/**
 * 创建或更新对话的执行计划
 */
export async function upsertPlan(
  conversationId: string,
  data: CoordinatorPlanData
): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  const planJson = data.plan as Prisma.InputJsonValue;
  const phaseOutputsJson = data.phaseOutputs
    ? (data.phaseOutputs as Prisma.InputJsonValue)
    : Prisma.JsonNull;

  try {
    await prisma.coordinatorPlan.upsert({
      where: { conversationId },
      update: {
        objective: data.objective,
        plan: planJson,
        activePhase: data.activePhase ?? null,
        completedPhases: data.completedPhases ?? [],
        phaseOutputs: phaseOutputsJson,
        status: data.status ?? 'running',
      },
      create: {
        conversationId,
        objective: data.objective,
        plan: planJson,
        activePhase: data.activePhase ?? null,
        completedPhases: data.completedPhases ?? [],
        phaseOutputs: phaseOutputsJson,
        status: data.status ?? 'running',
      },
    });

    logger.info({ conversationId }, 'Coordinator plan saved');
  } catch (err) {
    logger.error({ err, conversationId }, 'Failed to save coordinator plan');
    throw err;
  }
}

/**
 * 获取对话的执行计划
 */
export async function getPlan(conversationId: string) {
  const prisma = getPrisma();

  const plan = await prisma.coordinatorPlan.findUnique({
    where: { conversationId },
  });

  if (!plan) {
    return null;
  }

  return {
    id: plan.id,
    conversationId: plan.conversationId,
    objective: plan.objective,
    plan: plan.plan,
    activePhase: plan.activePhase,
    completedPhases: plan.completedPhases,
    phaseOutputs: plan.phaseOutputs,
    status: plan.status,
    createdAt: plan.createdAt.toISOString(),
    updatedAt: plan.updatedAt.toISOString(),
  };
}

/**
 * 更新 Phase 开始状态
 */
export async function updatePhaseStarted(
  conversationId: string,
  phaseIndex: number
): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  try {
    await prisma.coordinatorPlan.update({
      where: { conversationId },
      data: {
        activePhase: phaseIndex,
        status: 'running',
      },
    });

    logger.info({ conversationId, phaseIndex }, 'Phase started');
  } catch (err) {
    logger.error({ err, conversationId, phaseIndex }, 'Failed to update phase started');
  }
}

/**
 * 更新 Phase 完成状态
 */
export async function updatePhaseCompleted(
  conversationId: string,
  phaseIndex: number,
  phaseOutput?: Record<string, unknown>
): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  try {
    // 获取当前计划
    const existingPlan = await prisma.coordinatorPlan.findUnique({
      where: { conversationId },
    });

    if (!existingPlan) {
      logger.warn({ conversationId, phaseIndex }, 'No plan found for phase completion');
      return;
    }

    // 更新已完成的 phases
    const completedPhases = existingPlan.completedPhases ?? [];
    if (!completedPhases.includes(phaseIndex)) {
      completedPhases.push(phaseIndex);
    }

    // 合并 phase outputs
    const existingOutputs = (existingPlan.phaseOutputs as Record<string, unknown>) ?? {};
    const phaseOutputs = { ...existingOutputs };
    if (phaseOutput) {
      phaseOutputs[`phase_${phaseIndex}`] = phaseOutput;
    }

    await prisma.coordinatorPlan.update({
      where: { conversationId },
      data: {
        completedPhases,
        phaseOutputs: phaseOutputs as Prisma.InputJsonValue,
        // 如果当前活跃 phase 是已完成的，清除活跃状态
        activePhase: existingPlan.activePhase === phaseIndex ? null : existingPlan.activePhase,
      },
    });

    logger.info({ conversationId, phaseIndex, completedCount: completedPhases.length }, 'Phase completed');
  } catch (err) {
    logger.error({ err, conversationId, phaseIndex }, 'Failed to update phase completed');
  }
}

/**
 * 更新计划整体状态
 */
export async function updatePlanStatus(
  conversationId: string,
  status: 'running' | 'completed' | 'failed'
): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  try {
    await prisma.coordinatorPlan.update({
      where: { conversationId },
      data: { status },
    });

    logger.info({ conversationId, status }, 'Plan status updated');
  } catch (err) {
    logger.error({ err, conversationId, status }, 'Failed to update plan status');
  }
}

/**
 * 删除对话的执行计划
 */
export async function deletePlan(conversationId: string): Promise<void> {
  const prisma = getPrisma();
  const logger = getLogger();

  try {
    await prisma.coordinatorPlan.delete({
      where: { conversationId },
    });

    logger.info({ conversationId }, 'Coordinator plan deleted');
  } catch (err) {
    // 如果不存在则忽略
    logger.debug({ err, conversationId }, 'Plan delete skipped (may not exist)');
  }
}
