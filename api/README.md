# Orchestrate API

## Reference
Based on this sample repo https://github.com/GoogleCloudPlatform/python-docs-samples/tree/master/endpoints/getting-started-grpc

There are automation scripts in the bin directory to manage the API
implementation deployment.

## Basic operations

1. Create cluster:

    ```sh
    bin/create_cluster.sh
    ```

    Run once to create the GKE cluster.

2. Update cluster

    ```sh
    bin/update_cluster.sh
    ```

    Run to deploy implementation changes, automatically compiles protos and
    deploys changes to enpoints.

## Additional operations

1. Compile protos

    ```sh
    bin/compile_protos.sh
    ```

    Run every time protos change.

2. Deploy endpoints

    ```sh
    bin/deploy_endpoints.sh
    ```

    Run to deploy changes to the endpoints service.

## Testing

```sh
bin/get_api_url.sh
```

Returns the load balancer's IP address and port where the API is available.

```sh
ORCHESTRATE_API_URL=LoadBalancerIP:80
API_KEY=GetOneFromConsoleCredentials
python test_orchestrate.py --host=$ORCHESTRATE_API_URL --api_key=$API_KEY
```
