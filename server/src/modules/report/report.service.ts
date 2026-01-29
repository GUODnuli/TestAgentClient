import path from 'path';
import fs from 'fs';
import { getConfig } from '../../config/index.js';
import { NotFoundError } from '../../common/errors.js';

export async function getReportData(taskId: string) {
  const config = getConfig();
  const reportsDir = path.resolve(config.storage.root, 'tasks', taskId, 'reports');

  if (!fs.existsSync(reportsDir)) {
    throw new NotFoundError('报告');
  }

  // Find latest JSON report
  const files = fs.readdirSync(reportsDir).filter((f) => f.endsWith('.json'));
  if (files.length === 0) {
    throw new NotFoundError('报告');
  }

  const latestFile = files.sort().reverse()[0];
  const filePath = path.join(reportsDir, latestFile);

  // Path security
  const storageRoot = path.resolve(config.storage.root);
  if (!path.resolve(filePath).startsWith(storageRoot)) {
    throw new NotFoundError('报告');
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  return JSON.parse(content);
}

export async function getMarkdownReport(taskId: string) {
  const config = getConfig();
  const reportsDir = path.resolve(config.storage.root, 'tasks', taskId, 'reports');

  if (!fs.existsSync(reportsDir)) {
    throw new NotFoundError('报告');
  }

  const files = fs.readdirSync(reportsDir).filter((f) => f.endsWith('.md'));
  if (files.length === 0) {
    throw new NotFoundError('Markdown 报告');
  }

  const latestFile = files.sort().reverse()[0];
  const filePath = path.join(reportsDir, latestFile);

  const storageRoot = path.resolve(config.storage.root);
  if (!path.resolve(filePath).startsWith(storageRoot)) {
    throw new NotFoundError('报告');
  }

  return fs.readFileSync(filePath, 'utf-8');
}
