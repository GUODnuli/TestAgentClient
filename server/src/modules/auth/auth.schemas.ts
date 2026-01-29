import { z } from 'zod';

export const registerSchema = z.object({
  username: z
    .string()
    .min(4, '用户名至少4个字符')
    .max(32, '用户名最多32个字符')
    .regex(/^[a-zA-Z][a-zA-Z0-9_]*$/, '用户名必须以字母开头，只能包含字母、数字和下划线'),
  password: z.string().min(8, '密码长度至少8位').max(128, '密码最多128个字符'),
  email: z.string().email('邮箱格式无效').nullable().optional(),
  display_name: z.string().max(64, '显示名称最多64个字符').nullable().optional(),
});

export const loginSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
  password: z.string().min(1, '请输入密码'),
});

export const changePasswordSchema = z.object({
  old_password: z.string().min(1, '请输入旧密码'),
  new_password: z.string().min(8, '新密码长度至少8位').max(128, '新密码最多128个字符'),
});

export const updateProfileSchema = z.object({
  display_name: z.string().max(64).nullable().optional(),
  email: z.string().email().nullable().optional(),
});

export const updateUserStatusSchema = z.object({
  new_status: z.enum(['active', 'inactive', 'banned']),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;
export type UpdateProfileInput = z.infer<typeof updateProfileSchema>;
