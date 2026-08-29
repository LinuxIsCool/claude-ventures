/**
 * App: a deployable application a venture is building. Sibling of Project
 * in the fractal tree. Lives at ~/.claude/local/ventures/{venture}/apps/{slug}/app.md.
 * Spec: backlog task-824 section 6.1.
 */

export type AppKind = "web" | "api" | "static" | "pipeline" | "library";
export type AppStage = "planned" | "active" | "paused" | "retired";
export type RuntimeKind = "compose" | "process" | "none";

export interface AppRepo {
  path: string;                     // local checkout, may start with ~
  remote?: string;                  // owner/name on the canonical forge
  default_branch?: string;
  vcs?: "git" | "jj+git";
}

export interface AppEnvironment {
  name: string;                     // dev | staging | prod | demo | ...
  url?: string;
  host?: string;                    // legion2, netcup, vercel, ...
  healthz?: string;                 // path appended to url
  deploy?: "compose" | "vercel" | "pages" | "nginx" | "manual";
  status?: "live" | "unprovisioned" | "paused";
  controllable?: boolean;           // Studio may start/stop; default: name === "dev"
}

export interface AppRuntime {
  kind: RuntimeKind;
  file?: string;                    // compose file, relative to repo.path
  project?: string;                 // docker compose -p
  network?: string;
  hostname?: string;                // <app>.<env>.legion
}

export interface App {
  slug: string;
  name: string;
  venture: string;                  // FK venture slug
  project?: string;                 // FK project slug within the venture
  kind: AppKind;
  stage: AppStage;
  repo: AppRepo;
  run?: string;
  test?: string;
  status_doc?: string;              // path relative to repo.path
  environments: AppEnvironment[];
  depends_on: string[];             // app or infra slugs
  secrets?: string;                 // path only, never values
  runtime?: AppRuntime;
  notes?: string;                   // markdown body
  created_at: string;
  updated_at: string;
  file_path?: string;
}

export type CreateAppInput = Omit<App, "created_at" | "updated_at" | "file_path">;
export type UpdateAppInput = Partial<Omit<App, "slug" | "venture" | "created_at" | "file_path">>;

export interface AppFilter {
  venture?: string;
  project?: string;
  stage?: AppStage | AppStage[];
  kind?: AppKind | AppKind[];
}

export interface AppQuery {
  filter?: AppFilter;
  sort_by?: "name" | "created" | "updated";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

/** Studio may act on an environment only when this is true. */
export function isControllable(env: AppEnvironment): boolean {
  return env.controllable ?? env.name === "dev";
}
