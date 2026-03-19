import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import toast from "react-hot-toast";

import InputField from "../components/ui/InputField";
import Button from "../components/ui/Button";
import useAuthStore from "../store/authStore";
import { loginSchema } from "../utils/validationSchemas";

const TEXT = {
  title: "\uB85C\uADF8\uC778",
  email: "\uC774\uBA54\uC77C",
  password: "\uBE44\uBC00\uBC88\uD638",
  submit: "\uB85C\uADF8\uC778",
  noAccount: "\uACC4\uC815\uC774 \uC5C6\uC73C\uC2E0\uAC00\uC694?",
  register: "\uD68C\uC6D0\uAC00\uC785",
  success: "\uD658\uC601\uD569\uB2C8\uB2E4!",
  genericError: "\uB85C\uADF8\uC778\uC5D0 \uC2E4\uD328\uD588\uC2B5\uB2C8\uB2E4.",
  networkError:
    "\uC11C\uBC84\uC640 \uC5F0\uACB0\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4. \uC7A0\uC2DC \uD6C4 \uB2E4\uC2DC \uC2DC\uB3C4\uD574\uC8FC\uC138\uC694.",
};

export default function Login() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const [isLoading, setIsLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data) => {
    try {
      setIsLoading(true);

      const formData = new URLSearchParams();
      formData.append("username", data.email);
      formData.append("password", data.password);

      const response = await axios.post(
        "http://localhost:8000/api/auth/login",
        formData,
        {
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        }
      );

      const token = response.data?.access_token;
      const nickname = response.data?.nickname ?? "";

      if (!token) {
        setError("password", { type: "server", message: TEXT.genericError });
        return;
      }

      login(token, { email: data.email, nickname });
      toast.success(TEXT.success);
      navigate("/");
    } catch (error) {
      if (!error?.response) {
        toast.error(TEXT.networkError);
        return;
      }
      const backendMessage =
        error?.response?.data?.detail ||
        error?.response?.data?.message ||
        TEXT.genericError;

      setError("password", { type: "server", message: String(backendMessage) });
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
            label={TEXT.password}
            type="password"
            placeholder="비밀번호를 입력해주세요"
            error={errors.password?.message}
            {...register("password")}
          />

          <Button type="submit" isLoading={isLoading}>
            {TEXT.submit}
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-slate-400">
          {TEXT.noAccount}{" "}
          <Link to="/register" className="font-medium text-blue-400 hover:text-blue-300">
            {TEXT.register}
          </Link>
        </p>
      </div>
    </div>
  );
}
