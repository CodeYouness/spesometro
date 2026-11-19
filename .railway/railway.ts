import { defineRailway, github, project, service } from "railway/iac";
// This repository manages only its own resources in the environment. Other
// repositories export their own partial name.
// See https://docs.railway.com/infrastructure-as-code#multi-repo-projects
export const partial = "spesometro";
export default defineRailway(() => {
  const spesometro = service("spesometro", {
    source: github("CodeYouness/spesometro"),
    build: { buildEnvironment: "V3", builder: "DOCKERFILE", dockerfilePath: "docker/Dockerfile" },
    healthcheck: "/health",
    healthcheckTimeout: 60,
    // Sleeping spento e riavvio ON_FAILURE sono i default di Railway: dichiararli
    // qui lascia una differenza permanente in `railway config plan`.
    deploy: { restartPolicyMaxRetries: 3 },
    replicas: { "europe-west4-drams3a": 1 },
  });

  return project("spesometro", {
    variables: { managed: false },
    resources: [spesometro],
  });
});
