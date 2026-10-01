import subprocess
import json
import sys



NAMESPACE = "prod"
DEPLOYMENT = "node-app-prod"


def run_command(command):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Command failed:")
        print(result.stderr)
        sys.exit(1)

    return result.stdout

def check_service():
    output = run_command([
        "kubectl",
        "get",
        "service",
        DEPLOYMENT,
        "-n",
        NAMESPACE,
        "-o",
        "json"
    ])

    service = json.loads(output)

    service_type = service["spec"].get("type", "Unknown")
    cluster_ip = service["spec"].get("clusterIP", "None")

    print("\nService Status:")
    print(f"Service: {DEPLOYMENT}")
    print(f"Type: {service_type}")
    print(f"Cluster IP: {cluster_ip}")

    return True

def check_application():
    print("\nApplication Health:")

    output = run_command([
        "kubectl",
        "run",
        "health-check",
        "-n",
        NAMESPACE,
        "--rm",
        "-i",
        "--restart=Never",
        "--image=curlimages/curl",
        "--",
        "curl",
        "-s",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        f"http://{DEPLOYMENT}.{NAMESPACE}.svc.cluster.local/health"
    ])

    status_code = output.strip().split("pod")[0].strip()

    print(f"HTTP Status: {status_code}")

    return status_code == "200"

def check_deployment():
    output = run_command([
        "kubectl",
        "get",
        "deployment",
        DEPLOYMENT,
        "-n",
        NAMESPACE,
        "-o",
        "json"
    ])

    deployment = json.loads(output)

    replicas = deployment["spec"].get("replicas", 0)
    available = deployment["status"].get("availableReplicas", 0)

    print(f"Deployment: {DEPLOYMENT}")
    print(f"Namespace: {NAMESPACE}")
    print(f"Desired replicas: {replicas}")
    print(f"Available replicas: {available}")

    return available == replicas


def check_pods():
    output = run_command([
        "kubectl",
        "get",
        "pods",
        "-n",
        NAMESPACE,
        "-o",
        "json"
    ])

    pods = json.loads(output)

    print("\nPod Status:")

    all_healthy = True

    for pod in pods["items"]:
        name = pod["metadata"]["name"]
        phase = pod["status"].get("phase", "Unknown")

        restarts = 0

        for container in pod["status"].get("containerStatuses", []):
            restarts += container.get("restartCount", 0)

        print(f"{name} | Status: {phase} | Restarts: {restarts}")

        if phase != "Running":
            all_healthy = False

    return all_healthy


if __name__ == "__main__":
    deployment_healthy = check_deployment()
    pods_healthy = check_pods()
    service_healthy = check_service()
    application_healthy = check_application()

    print("\nOverall Status:")

    if (
        deployment_healthy
        and pods_healthy
        and service_healthy
        and application_healthy
    ):
        print("STATUS: HEALTHY")
    else:
        print("STATUS: UNHEALTHY")
        sys.exit(1)
