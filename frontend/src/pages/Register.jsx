import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import toast from "react-hot-toast";

import InputField from "../components/ui/InputField";
import Button from "../components/ui/Button";
import { registerSchema } from "../utils/validationSchemas";

const TEXT = {
  title: "\uD68C\uC6D0\uAC00\uC785",
  email: "\uC774\uBA54\uC77C",
  nickname: "\uB2C9\uB124\uC784",
  password: "\uBE44\uBC00\uBC88\uD638",
  passwordConfirm: "\uBE44\uBC00\uBC88\uD638 \uD655\uC778",
  submit: "\uAC00\uC785\uD558\uAE30",
  success: "\uD68C\uC6D0\uAC00\uC785\uC774 \uC644\uB8CC\uB418\uC5C8\uC2B5\uB2C8\uB2E4!",
  successNext: "\uD68C\uC6D0\uAC00\uC785\uC774 \uC644\uB8CC\uB418\uC5C8\uC2B5\uB2C8\uB2E4! \uB85C\uADF8\uC778\uD574\uC8FC\uC138\uC694.",
  genericError: "\uD68C\uC6D0\uAC00\uC785\uC5D0 \uC2E4\uD328\uD588\uC2B5\uB2C8\uB2E4.",
  networkError:
    "\uC11C\uBC84\uC640 \uC5F0\uACB0\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4. \uC7A0\uC2DC \uD6C4 \uB2E4\uC2DC \uC2DC\uB3C4\uD574\uC8FC\uC138\uC694.",
  hasAccount: "\uC774\uBBF8 \uACC4\uC815\uC774 \uC788\uC73C\uC2E0\uAC00\uC694?",
  login: "\uB85C\uADF8\uC778",
};

export default function Register() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data) => {
    try {
      setIsLoading(true);
      await axios.post("http://localhost:8000/api/auth/register", data);
      toast.success(TEXT.successNext);
      navigate("/login");
    } catch (error) {
      if (!error?.response) {
        toast.error(TEXT.networkError);
        return;
      }
      const responseData = error?.response?.data;
      const backendMessage =
        responseData?.detail || responseData?.message || TEXT.genericError;
      const normalized = String(backendMessage).toLowerCase();

      if (normalized.includes("email")) {
        setError("email", { type: "server", message: String(backendMessage) });
      } else if (normalized.includes("nickname") || normalized.includes("nick")) {
        setError("nickname", { type: "server", message: String(backendMessage) });
      } else {
        setError("email", { type: "server", message: String(backendMessage) });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-7 shadow-xl sm:p-8">
        <h1 className="mb-6 text-center text-2xl font-bold text-white">{TEXT.title}</h1>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <InputField
            label={TEXT.email}
            type="email"
            placeholder="이메일을 입력해주세요"
            error={errors.email?.message}
            {...register("email")}
          />
          <InputField
            label={TEXT.nickname}
            placeholder="사용할 닉네임을 입력해주세요"
            error={errors.nickname?.message}
            {...register("nickname")}
          />
          <InputField
            label={TEXT.password}
            type="password"
            placeholder="비밀번호 (8자 이상 영문/숫자)"
            error={errors.password?.message}
            {...register("password")}
          />
          <InputField
            label={TEXT.passwordConfirm}
            type="password"
            placeholder="비밀번호를 다시 입력해주세요"
            error={errors.passwordConfirm?.message}
            {...register("passwordConfirm")}
          />

          <Button type="submit" isLoading={isLoading}>
            {TEXT.submit}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-slate-400">
          {TEXT.hasAccount}{" "}
          <Link to="/login" className="font-medium text-blue-400 hover:text-blue-300">
            {TEXT.login}
          </Link>
        </p>
      </div>
    </div>
  );
}
