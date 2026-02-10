import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
});

export type LoginFormData = z.infer<typeof loginSchema>;

export const registerSchema = z
  .object({
    first_name: z.string().optional(),
    last_name: z.string().optional(),
    email: z.string().min(1, 'Email is required').email('Invalid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    password_confirm: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: 'Passwords do not match',
    path: ['password_confirm'],
  });

export type RegisterFormData = z.infer<typeof registerSchema>;

export const changePasswordSchema = z
  .object({
    old_password: z.string().default(''),
    new_password: z.string().min(8, 'Password must be at least 8 characters'),
    new_password_confirm: z.string().min(1, 'Please confirm your password'),
  })
  .refine((data) => data.new_password === data.new_password_confirm, {
    message: 'Passwords do not match',
    path: ['new_password_confirm'],
  });

export type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

export const courseSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  description: z.string().default(''),
  database_type: z.string().min(1, 'Database type is required'),
  enrollment_key: z.string().default(''),
  max_students: z.number().positive().optional().nullable(),
  start_date: z.string().default(''),
  end_date: z.string().default(''),
});

export type CourseFormData = z.infer<typeof courseSchema>;

export const lessonSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  description: z.string().default(''),
  lesson_type: z.enum(['theory', 'practice', 'mixed']),
  theory_content: z.string().default(''),
  practice_description: z.string().default(''),
  practice_initial_code: z.string().default(''),
  expected_query: z.string().default(''),
  required_keywords: z.array(z.string()).default([]),
  forbidden_keywords: z.array(z.string()).default([]),
  order_matters: z.boolean().default(false),
  max_score: z.number().positive().default(100),
  time_limit_seconds: z.number().positive().default(60),
  max_attempts: z.number().positive().optional().nullable(),
  hints: z.array(z.string()).default([]),
  dataset_id: z.string().optional().nullable(),
  module_id: z.string().optional().nullable(),
  is_published: z.boolean().default(false),
});

export type LessonFormData = z.infer<typeof lessonSchema>;

export const moduleSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  description: z.string().default(''),
  order: z.number().optional(),
  is_published: z.boolean().default(false),
});

export type ModuleFormData = z.infer<typeof moduleSchema>;
