# Complete AWS DevOps / Kubernetes / GitOps Project Runbook
## From source code to CI/CD, Helm, Argo CD, Kubernetes traffic, monitoring, automation, and Terraform

**Project:** `local-devops-project`  
**Repository:** https://github.com/kiranshet/local-devops-project  
**Branch:** `master`  
**Application:** Node.js REST service  
**Local Kubernetes:** Docker Desktop Kubernetes  
**Image registry:** GitHub Container Registry (GHCR)  
**GitOps:** Argo CD + Helm  
**Infrastructure as Code:** Terraform (AWS S3 demo resource)

> **Scope and accuracy:** This runbook documents the work completed in this project and the commands used during the lab. Kubernetes runs locally on Docker Desktop. The Terraform work in this repository creates an S3 bucket with versioning and server-side encryption. An AWS VPC, Transit Gateway, ALB, RDS, or EKS cluster was **not** created as part of this local project; those belong to the separate interview architecture discussion. Adapt commands and names to the current repository state if files have changed.

---

# 1. Project goals

The project demonstrates a practical DevOps delivery path:

1. Develop and test a Node.js application.
2. Build a Docker image.
3. Run automated tests in GitHub Actions.
4. Publish versioned images to GHCR.
5. package Kubernetes resources using Helm.
6. Deploy to Kubernetes.
7. Use Argo CD to reconcile the production release from Git.
8. Use readiness, liveness, and startup probes.
9. Configure CPU/memory requests and limits.
10. Configure an HPA and observe scale-out under load.
11. Monitor Kubernetes/application health with Prometheus/Grafana.
12. Run a Python production-health check.
13. Provision an AWS S3 resource using Terraform.

## High-level architecture

```text
Developer
   |
   | git push to master
   v
GitHub repository
   |
   v
GitHub Actions CI
   |-- checkout source
   |-- install Node.js
   |-- npm ci
   |-- npm test
   |-- build Docker image
   |-- push image to GHCR using commit SHA
   |-- update Helm production image tag in Git
   v
Git repository (Helm values updated)
   |
   v
Argo CD watches Git
   |-- reads Helm chart
   |-- applies desired Kubernetes resources
   |-- detects drift and self-heals
   v
Docker Desktop Kubernetes
   |
   | Service DNS / ClusterIP :80
   v
Service -> Ready Pod IP:3000 -> Node.js application
   |
   +--> /health endpoint

Prometheus metrics -> Grafana dashboards
Python health-check script -> Kubernetes API + application health endpoint

Terraform -> AWS S3 bucket (versioning + AES256 encryption)
```

---

# 2. Repository layout

The project includes these main paths:

```text
local-devops-project/
├── .github/
│   └── workflows/
│       └── ci.yml
├── GitOps/
│   └── prod/
│       └── application.yaml
├── app/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   ├── server.js
│   └── server.test.js
├── helm/
│   └── node-app/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-dev.yaml
│       ├── values-prod.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           └── hpa.yaml
├── k8s/
│   ├── dev/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── prod/
├── scripts/
│   └── check_prod_health.py
└── terraform/
    ├── provider.tf
    ├── variables.tf
    ├── main.tf
    └── .terraform.lock.hcl
```

---

# 3. Verify the workstation and tools

Run from WSL/Linux terminal:

```bash
pwd
git --version
docker --version
kubectl version --client
kubectl config current-context
kubectl get nodes
helm version
terraform version
python3 --version
node --version
npm --version
```

Expected context for the local lab:

```text
docker-desktop
```

Check cluster nodes:

```bash
kubectl get nodes -o wide
```

The lab used Docker Desktop Kubernetes with nodes such as `desktop-control-plane` and `desktop-worker`.

Check namespaces and workloads:

```bash
kubectl get namespaces
kubectl get pods -A
```

---

# 4. Application: Node.js service

The app is a Node.js service listening on port `3000`. The health endpoint is:

```text
GET /health
```

Expected response:

```json
{"status":"healthy"}
```

Inspect the application files:

```bash
cd /mnt/c/Users/Dell/local-devops-project
cat app/package.json
cat app/server.js
cat app/server.test.js
```

Install dependencies and run tests locally:

```bash
cd app
npm ci
npm test
```

Return to the repository root:

```bash
cd ..
```

**Why this matters:** tests catch application regressions before the image is built and deployed.

---

# 5. Docker image

Inspect the Dockerfile:

```bash
cat app/Dockerfile
```

Build a local image for a quick check:

```bash
docker build -t node-app:local ./app
```

Run it locally:

```bash
docker run --rm -d --name node-app-local -p 3000:3000 node-app:local
```

Test the endpoint:

```bash
curl -i http://localhost:3000/health
```

Stop the test container:

```bash
docker stop node-app-local
```

**Image tagging rule:** CI publishes the image to GHCR with the Git commit SHA. A commit SHA is immutable and makes a deployment traceable to source code.

Image naming pattern:

```text
ghcr.io/kiranshet/local-devops-project:<git-commit-sha>
```

---

# 6. CI pipeline: GitHub Actions

Workflow file:

```text
.github/workflows/ci.yml
```

Inspect it:

```bash
cat .github/workflows/ci.yml
```

The completed workflow performs these stages:

1. Trigger on push or pull request to `master`.
2. Check out the repository.
3. Set up Node.js 24 and npm cache.
4. Run `npm ci`.
5. Run `npm test`.
6. Log in to GHCR using `GITHUB_TOKEN`.
7. Build the Docker image.
8. Push the image using the commit SHA tag.
9. For pushes to `master`, update `helm/node-app/values-prod.yaml` to the new image SHA and commit that change.

Simplified pipeline:

```text
Git push / pull request
        |
        v
Checkout source
        |
        v
Setup Node.js
        |
        v
npm ci
        |
        v
npm test
        |
        v
Docker build
        |
        v
Push image to GHCR
        |
        v
Update production Helm image tag (master push)
```

## GitHub Actions verification

Open the repository's **Actions** tab and inspect the latest workflow run. Confirm that the install, test, login, build, and push steps completed successfully.

You can also inspect the latest commit and working tree locally:

```bash
git status
git log -5 --oneline
```

## Important CI/CD detail

The workflow updates the production image tag in Git. Argo CD then detects that Git change and reconciles the Kubernetes release. This is GitOps: Git is the desired-state source, and Argo CD continuously compares live state with that desired state.

---

# 7. Helm chart

Chart directory:

```text
helm/node-app
```

Inspect chart files:

```bash
cat helm/node-app/Chart.yaml
cat helm/node-app/values.yaml
cat helm/node-app/values-dev.yaml
cat helm/node-app/values-prod.yaml
```

The chart separates reusable Kubernetes templates from environment-specific values.

- `values.yaml`: common defaults.
- `values-dev.yaml`: development overrides.
- `values-prod.yaml`: production overrides.
- `templates/deployment.yaml`: Deployment.
- `templates/service.yaml`: Service.
- `templates/hpa.yaml`: HorizontalPodAutoscaler.

## Validate the chart

```bash
helm lint ./helm/node-app
```

Render production YAML locally without deploying:

```bash
helm template node-app-prod ./helm/node-app \
  -n prod \
  -f helm/node-app/values-prod.yaml
```

Inspect only the HPA section:

```bash
helm template node-app-prod ./helm/node-app \
  -n prod \
  -f helm/node-app/values-prod.yaml \
  | grep -A20 -B2 "HorizontalPodAutoscaler"
```

## Production settings used in the lab

The production values were configured for:

- 3 baseline replicas.
- GHCR image repository and commit-SHA tag.
- Service port `80` targeting container port `3000`.
- CPU request `100m`; memory request `128Mi`.
- CPU limit `500m`; memory limit `256Mi`.
- HPA minimum 3 replicas, maximum 6.
- HPA CPU target 50%.

Always check the actual values file for the current image tag:

```bash
grep -A8 -B2 "image:" helm/node-app/values-prod.yaml
grep -A15 -B2 "autoscaling:" helm/node-app/values-prod.yaml
```

---

# 8. Kubernetes resources

## Namespace

Production namespace:

```bash
kubectl get namespace prod
```

If it does not exist in a fresh local cluster:

```bash
kubectl create namespace prod
```

Do not rerun the create command if the namespace already exists.

## Deployment

The Helm Deployment creates application Pods. Check it:

```bash
kubectl get deployment -n prod
kubectl get deployment node-app-prod -n prod -o wide
kubectl describe deployment node-app-prod -n prod
```

Check rollout:

```bash
kubectl rollout status deployment/node-app-prod -n prod
kubectl rollout history deployment/node-app-prod -n prod
```

## Pods

```bash
kubectl get pods -n prod -o wide
kubectl describe pods -n prod
kubectl logs deployment/node-app-prod -n prod
```

Follow logs:

```bash
kubectl logs -f deployment/node-app-prod -n prod
```

For a specific Pod:

```bash
kubectl logs <pod-name> -n prod
kubectl describe pod <pod-name> -n prod
```

## Service

```bash
kubectl get service -n prod
kubectl describe service node-app-prod -n prod
```

The Service exposes port `80` inside the cluster and forwards traffic to the application container's port `3000`.

## EndpointSlices

EndpointSlices show the backend Pod IPs selected by a Service:

```bash
kubectl get endpointslice -n prod
kubectl get endpointslice -n prod -o yaml
```

Look for ready endpoints. Pods that fail readiness checks should not receive normal Service traffic.

---

# 9. Traffic flow: request to Pod

For the local project, traffic is sent to the Kubernetes Service from inside the cluster.

```text
curl / client Pod
      |
      | http://node-app-prod:80
      v
Kubernetes Service (ClusterIP, port 80)
      |
      | selects Ready endpoints
      v
Service dataplane rules
      |
      | forwards to one selected Pod IP:3000
      v
Node.js container
      |
      v
GET /health -> HTTP 200
```

## Test the Service from inside Kubernetes

Create a temporary curl Pod:

```bash
kubectl run traffic-test \
  -n prod \
  --image=curlimages/curl:latest \
  --restart=Never \
  --command -- sh -c 'curl -sS -v http://node-app-prod:80/health'
```

Check its output:

```bash
kubectl logs traffic-test -n prod
```

Expected application response:

```json
{"status":"healthy"}
```

Clean up:

```bash
kubectl delete pod traffic-test -n prod
```

If a temporary Pod is still terminating, check:

```bash
kubectl get pod traffic-test -n prod
```

## What happens behind the Service?

A Kubernetes Service provides a stable virtual IP and DNS name. The control plane maintains EndpointSlices for matching Pods. On this Docker Desktop cluster, kube-proxy was observed using iptables rules to direct Service traffic to Pod endpoints.

Inspect kube-proxy:

```bash
kubectl get configmap kube-proxy -n kube-system -o yaml
kubectl get pods -n kube-system -l k8s-app=kube-proxy
```

Inspect EndpointSlices:

```bash
kubectl get endpointslice -n prod -o yaml
```

**Interview detail:** kube-proxy programs the dataplane rules; the Linux kernel/netfilter processes packets. Do not describe kube-proxy as a userspace proxy handling every packet in iptables mode.

**Scope note:** this local flow uses an internal ClusterIP Service. It does not include Route 53, a public ALB, or an AWS VPC. In a typical AWS EKS web architecture, external DNS and an ALB/Ingress layer may sit before the Kubernetes Service.

---

# 10. Readiness, liveness, and startup probes

These probes were tested with temporary lab Deployments.

## Readiness probe

Purpose: determine whether a container should receive Service traffic.

A deliberately invalid readiness path was tested:

```yaml
readinessProbe:
  httpGet:
    path: /does-not-exist
    port: 3000
  initialDelaySeconds: 2
  periodSeconds: 5
  failureThreshold: 1
```

Observed behavior:
- Pod remained Running.
- Ready status became false (`0/1`).
- Restart count did not increase.
- The Pod was removed from ready Service endpoints.
- Requests continued to reach healthy Ready Pods.

Commands to investigate:

```bash
kubectl get pods -n prod
kubectl describe pod <pod-name> -n prod
kubectl get endpointslice -n prod -o yaml
```

## Liveness probe

Purpose: detect a container that is stuck and should be restarted.

A deliberately invalid liveness path was tested:

```yaml
livenessProbe:
  httpGet:
    path: /does-not-exist
    port: 3000
  initialDelaySeconds: 2
  periodSeconds: 5
  failureThreshold: 1
```

Observed behavior:
- Liveness checks failed.
- The container restarted.
- Repeated failures led to CrashLoopBackOff.

Check:

```bash
kubectl describe pod <pod-name> -n prod
kubectl logs <pod-name> -n prod --previous
```

## Startup probe

Purpose: give a slow-starting application time to initialize before liveness/readiness checks begin.

A startup probe was tested with an invalid path and a bounded failure window:

```yaml
startupProbe:
  httpGet:
    path: /does-not-exist
    port: 3000
  failureThreshold: 6
  periodSeconds: 5
```

When the startup probe fails for its configured threshold, kubelet restarts the container. In a real application, use a valid startup endpoint and tune the threshold for expected initialization time.

### Probe summary

| Probe | Main purpose | On failure |
|---|---|---|
| Readiness | Should this Pod receive traffic? | Pod is not Ready; normally no restart |
| Liveness | Is the container unhealthy/stuck? | Kubelet restarts the container after threshold |
| Startup | Has the application finished starting? | Liveness/readiness are held back until startup succeeds; threshold failure restarts |

---

# 11. Resource requests and limits

Production chart values used:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

Meaning:
- **Request**: scheduling reservation / baseline resource requirement used by the scheduler.
- **CPU limit**: caps CPU usage; excess CPU is throttled.
- **Memory limit**: exceeding the limit can result in an OOM kill.

Inspect actual Pod resource settings:

```bash
kubectl get pods -n prod
kubectl describe pod <pod-name> -n prod
```

Check live usage after Metrics Server is available:

```bash
kubectl top pods -n prod
kubectl top nodes
```

---

# 12. Metrics Server on Docker Desktop

Metrics Server was installed to enable `kubectl top` and HPA CPU metrics.

Install:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Check status:

```bash
kubectl get deployment metrics-server -n kube-system
kubectl get pods -n kube-system | grep metrics-server
kubectl logs deployment/metrics-server -n kube-system
```

## Local Docker Desktop certificate workaround

In this lab, Metrics Server initially could not verify the kubelet certificate because the kubelet address did not match an IP SAN. The following local-only patch was used:

```bash
kubectl patch deployment metrics-server -n kube-system --type='strategic' -p '
spec:
  template:
    spec:
      containers:
      - name: metrics-server
        args:
        - --cert-dir=/tmp
        - --secure-port=10250
        - --kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname
        - --kubelet-use-node-status-port
        - --metric-resolution=15s
        - --kubelet-insecure-tls
'
```

Then verify:

```bash
kubectl rollout status deployment/metrics-server -n kube-system
kubectl top nodes
kubectl top pods -A
```

> **Security warning:** `--kubelet-insecure-tls` disables kubelet certificate verification. It was used only to get metrics working in this local Docker Desktop lab. Do not copy this setting into production EKS. Production should use correctly configured and verified TLS.

---

# 13. Horizontal Pod Autoscaler (HPA)

The Helm HPA uses CPU utilization as its scaling signal:

- minimum replicas: 3
- maximum replicas: 6
- target CPU utilization: 50%

Check HPA:

```bash
kubectl get hpa -n prod
kubectl describe hpa node-app-prod -n prod
```

Check CPU metrics:

```bash
kubectl top pods -n prod
```

## Load test performed

A temporary request loop was used to create traffic:

```bash
kubectl run hpa-load \
  -n prod \
  --image=curlimages/curl:latest \
  --restart=Never \
  --command -- sh -c 'while true; do curl -s http://node-app-prod:80/health > /dev/null; done'
```

Additional load Pods were created:

```bash
for i in 1 2 3 4 5; do
  kubectl run hpa-load-$i \
    -n prod \
    --image=curlimages/curl:latest \
    --restart=Never \
    --command -- sh -c 'while true; do curl -s http://node-app-prod:80/health > /dev/null; done'
done
```

Watch HPA and Pods:

```bash
kubectl get hpa -n prod -w
kubectl get pods -n prod -w
```

The lab observed CPU utilization rise above the 50% target and the Deployment scale from 3 replicas up to 6.

## Clean up load generators

```bash
kubectl delete pod hpa-load hpa-load-1 hpa-load-2 hpa-load-3 hpa-load-4 hpa-load-5 -n prod
```

Observe scale-down:

```bash
kubectl get hpa -n prod -w
kubectl get deployment node-app-prod -n prod -w
```

Scale-down is not always immediate. HPA uses stabilization behavior to avoid rapidly oscillating replica counts.

## HPA and GitOps ownership

HPA updates the Deployment's `spec.replicas`. Helm has a baseline replica count. If Argo CD continually tries to restore the Helm replica count, it can conflict with HPA.

The Argo CD Application therefore ignores the Deployment replica field:

```yaml
ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
      - /spec/replicas
```

And includes:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
  syncOptions:
    - RespectIgnoreDifferences=true
```

This allows Argo CD to manage the rest of the Deployment while HPA manages replica count.

---

# 14. Argo CD and GitOps

Argo CD was installed in the `argocd` namespace.

Check installation:

```bash
kubectl get namespace argocd
kubectl get pods -n argocd
```

The installation command used was:

```bash
kubectl create namespace argocd
kubectl apply --server-side --force-conflicts -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

> If `argocd` already exists, skip the `kubectl create namespace` command.

Application manifest:

```text
GitOps/prod/application.yaml
```

It points Argo CD at:
- repository: `https://github.com/kiranshet/local-devops-project.git`
- branch: `master`
- chart path: `helm/node-app`
- values file: `values-prod.yaml`
- destination namespace: `prod`

It enables automated sync, pruning, and self-healing.

Apply/update the Application resource:

```bash
kubectl apply -f GitOps/prod/application.yaml
```

Check Application status:

```bash
kubectl get applications -n argocd
kubectl describe application node-app-prod -n argocd
```

The completed state was:

```text
node-app-prod   Synced   Healthy
```

## GitOps operating model

```text
Git desired state
      |
      v
Argo CD compares Git with cluster
      |
      +--> Synced: desired and live resources match
      |
      +--> OutOfSync: drift or Git changes need reconciliation
      |
      v
Argo CD syncs resources
      |
      v
Healthy: workload health checks pass
```

**Important:** `GitOps/prod/application.yaml` is itself a Kubernetes Application resource. In this setup, changing the YAML in Git does not automatically change the already-running Application object unless something applies that manifest. The update was applied with `kubectl apply -f GitOps/prod/application.yaml`.

---

# 15. Git synchronization when CI changes the repository

The GitHub Actions workflow can commit a new production image tag. If you also have local commits, a push may be rejected because the remote branch has advanced.

Safe recovery:

```bash
git status
git fetch origin
git pull --rebase origin master
git push origin master
```

If there is a rebase conflict:
1. Inspect conflicted files with `git status`.
2. Edit the files and resolve conflict markers.
3. Stage resolved files with `git add <file>`.
4. Continue with `git rebase --continue`.
5. Run tests / validate YAML as appropriate.
6. Push with `git push origin master`.

Avoid `git push --force` for this shared CI-updated branch unless there is a deliberate, reviewed reason.

---

# 16. Monitoring with Prometheus and Grafana

The project included a custom production Grafana dashboard with eight panels:

1. Production Pod Count
2. CPU
3. Memory
4. Ready Pods
5. Network Receive
6. Network Transmit
7. Pod Restarts
8. Unhealthy Pods

Conceptual flow:

```text
Kubernetes workloads / metrics
            |
            v
        Prometheus
            |
            | PromQL queries
            v
          Grafana
            |
            v
 Production dashboard / visual alerts
```

Useful Kubernetes checks alongside the dashboard:

```bash
kubectl get pods -n prod
kubectl top pods -n prod
kubectl top nodes
kubectl get deployment node-app-prod -n prod
kubectl get hpa node-app-prod -n prod
```

An unhealthy-Pod PromQL expression used in the dashboard was:

```promql
count(kube_pod_status_phase{namespace="prod",phase!="Running"} == 1) or vector(0)
```

**Interpretation:** count Pods in a non-Running phase in the `prod` namespace, returning zero if the query has no matching series. For a production dashboard, validate metric labels and semantics against the installed kube-state-metrics version; a Pod can be Running but not Ready, so use a separate Ready-Pod panel as well.

This runbook records the completed dashboard panels and query. It does not assume a particular Prometheus/Grafana installation command because the exact installation method is not part of the confirmed project notes.

---

# 17. Python production health-check automation

Script:

```text
scripts/check_prod_health.py
```

It checks:
- Deployment desired and available replicas.
- Pod phase and restart counts.
- Service type and ClusterIP.
- Application `/health` endpoint through a temporary curl Pod.
- Overall health summary.

Run from the repository root:

```bash
python3 scripts/check_prod_health.py
```

If it reports a problem, inspect the affected resources:

```bash
kubectl get deployment,pods,service,hpa -n prod
kubectl describe deployment node-app-prod -n prod
kubectl describe pods -n prod
kubectl logs deployment/node-app-prod -n prod
kubectl get endpointslice -n prod
kubectl top pods -n prod
```

The script is a lightweight operational check; it does not replace Prometheus alerting, application-level telemetry, or a production incident process.

---

# 18. Terraform: AWS S3 resource

The Terraform lab in this repository creates an AWS S3 bucket, enables versioning, and configures server-side encryption with AES256.

Files:

```text
terraform/provider.tf
terraform/variables.tf
terraform/main.tf
terraform/.terraform.lock.hcl
```

Inspect them:

```bash
cd /mnt/c/Users/Dell/local-devops-project/terraform
cat provider.tf
cat variables.tf
cat main.tf
```

The AWS provider region default is `ap-south-1` (Mumbai). Confirm the selected region and AWS identity before applying:

```bash
aws sts get-caller-identity
aws configure list
```

Do not paste AWS access keys into source files or commit them to Git. Use an approved credential mechanism such as an AWS profile or environment/role-based credentials.

## Terraform lifecycle

Initialize providers:

```bash
terraform init
```

Format:

```bash
terraform fmt
```

Validate:

```bash
terraform validate
```

Review planned changes:

```bash
terraform plan
```

Create the resource:

```bash
terraform apply
```

Review state:

```bash
terraform state list
terraform show
```

The bucket configuration uses a generated prefix to avoid hard-coding a globally unique bucket name. It enables:
- S3 bucket versioning.
- Default server-side encryption using `AES256`.

## Verify S3 settings

List buckets:

```bash
aws s3 ls
```

Find the bucket name from Terraform state/output or the AWS console, then verify versioning:

```bash
aws s3api get-bucket-versioning --bucket <bucket-name>
```

Verify encryption:

```bash
aws s3api get-bucket-encryption --bucket <bucket-name>
```

Expected encryption algorithm:

```text
AES256
```

## Destroy lab resources when finished

Review what will be deleted:

```bash
terraform plan -destroy
```

Then destroy:

```bash
terraform destroy
```

Only destroy resources you own and intend to remove. Confirm the AWS account and region first.

**Scope boundary:** this project’s confirmed Terraform implementation is the S3 resource. It does not provision an EKS cluster, VPC, subnets, NAT Gateway, Transit Gateway, Direct Connect, or RDS. Those are valuable next Terraform exercises, but should be documented as future work unless actually implemented.

---

# 19. Troubleshooting checklist

## Pod is Pending

```bash
kubectl describe pod <pod-name> -n prod
kubectl get events -n prod --sort-by=.lastTimestamp
kubectl describe nodes
```

Check scheduling constraints, available capacity, resource requests, PVCs, and image pull errors.

## Pod is CrashLoopBackOff

```bash
kubectl describe pod <pod-name> -n prod
kubectl logs <pod-name> -n prod
kubectl logs <pod-name> -n prod --previous
```

Check application startup, command/arguments, environment variables, probes, resource limits, and dependencies.

## Service returns no endpoints

```bash
kubectl describe service node-app-prod -n prod
kubectl get endpointslice -n prod -o yaml
kubectl get pods -n prod --show-labels
```

Check Service selectors, Pod labels, readiness, and target port.

## HPA does not scale

```bash
kubectl get hpa -n prod
kubectl describe hpa node-app-prod -n prod
kubectl top pods -n prod
kubectl get deployment node-app-prod -n prod
```

Check Metrics Server health, CPU requests, HPA events, and whether load is actually CPU-intensive. A request loop against a lightweight endpoint may generate network traffic without much CPU load.

## Argo CD shows OutOfSync

```bash
kubectl get applications -n argocd
kubectl describe application node-app-prod -n argocd
```

Check whether:
- Git changed.
- Live resources drifted.
- HPA owns `spec.replicas`.
- The live Application was updated after its YAML changed.
- Helm values or image tags are inconsistent.

## ImagePullBackOff

```bash
kubectl describe pod <pod-name> -n prod
```

Check the image repository/tag, GHCR package visibility, and image pull credentials if the package is private.

## Application health check fails

```bash
kubectl logs deployment/node-app-prod -n prod
kubectl get pods -n prod
kubectl get endpointslice -n prod
kubectl run traffic-test -n prod --image=curlimages/curl:latest --restart=Never --command -- sh -c 'curl -sS -v http://node-app-prod:80/health'
```

Clean up the temporary test Pod:

```bash
kubectl delete pod traffic-test -n prod
```

---

# 20. Daily verification commands

Run these from the repository root:

```bash
git status
kubectl get nodes
kubectl get pods -n prod -o wide
kubectl get deployment node-app-prod -n prod
kubectl get service node-app-prod -n prod
kubectl get endpointslice -n prod
kubectl get hpa node-app-prod -n prod
kubectl top pods -n prod
kubectl get applications -n argocd
python3 scripts/check_prod_health.py
```

Validate Helm:

```bash
helm lint ./helm/node-app
helm template node-app-prod ./helm/node-app -n prod -f helm/node-app/values-prod.yaml
```

Validate Terraform without changing infrastructure:

```bash
cd terraform
terraform fmt -check
terraform validate
terraform plan
```

---

# 21. End-to-end flows to explain in an interview

## CI/CD and GitOps flow

1. A developer pushes code to `master`.
2. GitHub Actions checks out the code and installs dependencies.
3. Unit tests run.
4. Docker builds the application image.
5. The image is pushed to GHCR with the commit SHA.
6. CI updates the production Helm values with that SHA and commits the change.
7. Argo CD detects the Git change.
8. Argo CD renders the Helm chart and reconciles Kubernetes resources.
9. Kubernetes creates/updates the Deployment and Pods.
10. Readiness probes determine which Pods receive Service traffic.
11. Monitoring and the health-check script help verify the release.

## Runtime request flow

1. A client Pod calls `http://node-app-prod:80/health`.
2. Kubernetes DNS resolves the Service name.
3. The Service virtual IP and dataplane rules direct traffic to a Ready endpoint.
4. The request reaches a Pod IP on port `3000`.
5. Node.js returns `{"status":"healthy"}`.
6. EndpointSlices and Pod readiness determine which backends are eligible.

## Autoscaling flow

1. Metrics Server collects node and Pod resource metrics.
2. HPA compares observed CPU utilization with the 50% target.
3. When demand is sufficiently high, HPA increases desired replicas up to 6.
4. Kubernetes schedules additional Pods.
5. Readiness probes gate traffic to newly created Pods.
6. When load drops, HPA scales down subject to stabilization behavior.
7. Argo CD ignores Deployment `spec.replicas`, so it does not fight HPA.

## Terraform flow

1. Configure AWS credentials and region.
2. `terraform init` downloads the provider.
3. `terraform fmt` formats code.
4. `terraform validate` checks configuration.
5. `terraform plan` previews changes.
6. `terraform apply` creates the S3 bucket and its configuration.
7. AWS CLI verifies versioning and encryption.
8. `terraform destroy` removes the lab resources when no longer needed.

---

# 22. Completed work summary

| Area | Completed work |
|---|---|
| Application | Node.js app with `/health` endpoint and tests |
| Container | Docker image build and GHCR image publishing |
| CI | GitHub Actions dependency install, tests, image build/push |
| CD / GitOps | Argo CD Application tracking Git and reconciling Helm |
| Helm | Reusable chart with Deployment, Service, and HPA templates |
| Kubernetes | Local Docker Desktop cluster, namespaces, Deployments, Pods, Service |
| Traffic | ClusterIP Service routing to Pod endpoints; curl test returned HTTP 200 |
| Probes | Readiness, liveness, and startup behavior tested |
| Resources | CPU/memory requests and limits configured |
| Autoscaling | HPA scaled from 3 to 6 during load test; load Pods cleaned up |
| GitOps/HPA | Argo CD configured to ignore Deployment replica drift |
| Metrics | Metrics Server enabled for `kubectl top` and HPA metrics |
| Monitoring | Custom Grafana production dashboard with eight panels |
| Automation | Python production health-check script |
| Terraform | AWS S3 bucket with versioning and AES256 encryption |
| AWS EKS/VPC | Not built in this project; keep separate from completed-work claims |

---

# 23. Two-minute project explanation

“I built a local DevOps project around a Node.js application and Docker Desktop Kubernetes. When code is pushed to the master branch, GitHub Actions installs dependencies, runs tests, builds a Docker image, and pushes it to GitHub Container Registry using the Git commit SHA. The workflow updates the production image tag in the Helm values file.

Argo CD watches the Git repository and deploys the Helm chart into the production namespace. The chart defines a Deployment, ClusterIP Service, resource requests and limits, and an HPA. The Service routes traffic to Ready Pods on port 3000, while clients access the service on port 80. I tested the application health endpoint from inside the cluster.

I also tested readiness, liveness, and startup probes, enabled Metrics Server, and used CPU-based HPA to scale the application from three to six replicas under load. Since HPA owns the replica count, I configured Argo CD to ignore the Deployment’s replica field so GitOps would not fight autoscaling. I created a Grafana production dashboard, wrote a Python health-check script, and used Terraform to provision an S3 bucket with versioning and AES256 encryption. The Kubernetes environment is local; the Terraform resource is in AWS, and I have not represented this project as an AWS EKS/VPC deployment.”

---

# 24. Production hardening opportunities (not claimed as completed)

These are potential next steps, not part of the completed-work list above:

- Add a pull-request approval and protected-branch policy.
- Add image vulnerability scanning and SBOM generation to CI.
- Sign images and verify signatures before deployment.
- Use a private GHCR package with a Kubernetes image pull secret or a registry integration.
- Add external secret management with AWS Secrets Manager and an appropriate identity mechanism.
- Add ingress/TLS and an external entry point if moving from local Kubernetes to EKS.
- Provision VPC, private/public subnets, route tables, endpoints/NAT, EKS, and supporting IAM with Terraform.
- Add alert rules, notification routing, and a documented incident runbook.
- Add automated rollback or progressive delivery after validating health checks.
- Store Terraform state remotely with locking and restricted access before team/production use.
