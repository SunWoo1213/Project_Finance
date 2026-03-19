import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("유효한 이메일 주소를 입력해주세요."),
  password: z.string().min(1, "비밀번호를 입력해주세요."),
});

export const registerSchema = z
  .object({
    email: z.string().email("유효한 이메일 주소를 입력해주세요."),
    nickname: z
      .string()
      .min(2, "닉네임은 최소 2자 이상이어야 합니다.")
      .max(10, "닉네임은 최대 10자까지 가능합니다."),
    password: z
      .string()
      .min(8, "비밀번호는 최소 8자 이상이어야 합니다.")
      .regex(/[a-zA-Z0-9]/, "영문과 숫자를 조합해주세요."),
    passwordConfirm: z.string().min(1, "비밀번호 확인을 입력해주세요."),
  })
  .refine((data) => data.password === data.passwordConfirm, {
    message: "비밀번호가 일치하지 않습니다.",
    path: ["passwordConfirm"],
  });
