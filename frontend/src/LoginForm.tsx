import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { login } from "./portfolioApi";

export default function LoginForm() {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const signIn = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: (me) => qc.setQueryData(["me"], me),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    signIn.mutate();
  };

  return (
    <div className="scroll">
      <form className="card login stack" onSubmit={submit}>
        <div>
          <h1>Log in</h1>
          <p className="lede">Log in to see and update your portfolio.</p>
        </div>
        <label className="field">
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
        </label>
        <label className="field">
          Password
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        <button className="primary" type="submit" disabled={signIn.isPending || !username || !password}>
          {signIn.isPending ? "Logging in…" : "Log in"}
        </button>
        {signIn.error && <p className="form-error">{(signIn.error as Error).message}</p>}
        <p className="muted">Accounts are created by whoever runs this app, from the backend folder.</p>
      </form>
    </div>
  );
}
