module.exports = {
  apps: [
    {
      name: "backend",
      cwd: "./packages/service",
      script: "uv",
      args: "run python main.py",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      stop_exit_codes: [0],
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
    {
      name: "frontend",
      cwd: "./packages/web",
      script: "bun",
      args: "run dev",
      autorestart: true,
      watch: false,
      max_restarts: 10,
      stop_exit_codes: [0],
    },
  ],
};
