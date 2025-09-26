"""Common module for tests."""

import sys
from pathlib import Path
from typing import cast

import boto3
from mypy_boto3_dynamodb import DynamoDBClient

sys.path.append(Path(__file__).parents[1].as_posix())
from google.protobuf.duration_pb2 import Duration
from job_manager.dynamodb_helper import DYNAMODB_JOB_TABLE_GSI_NAME
from moto import mock_aws
from pb.mqc3_cloud.common.v1 import math_pb2
from pb.mqc3_cloud.program.v1 import circuit_pb2, quantum_program_pb2
from pb.mqc3_cloud.scheduler.v1 import job_pb2
from utility import AWSCredentials


def construct_sample_program() -> quantum_program_pb2.QuantumProgram:
    circuit = circuit_pb2.CircuitRepresentation(
        n_modes=1,
        initial_states=[
            circuit_pb2.InitialState(
                bosonic=circuit_pb2.BosonicState(
                    gaussian_states=[
                        circuit_pb2.GaussianState(
                            mean=[math_pb2.Complex(real=0.0, imag=0.0)], cov=[0.05, 0.0, 0.0, 5.0]
                        )
                    ],
                    coeffs=[math_pb2.Complex(real=1.0, imag=0.0)],
                )
            )
        ],
        operations=[
            circuit_pb2.CircuitOperation(
                type=circuit_pb2.CircuitOperation.OPERATION_TYPE_DISPLACEMENT,
                modes=[0],
                parameters=[1.0, 0.0],
            )
        ],
    )

    return quantum_program_pb2.QuantumProgram(
        format=quantum_program_pb2.REPRESENTATION_FORMAT_CIRCUIT, circuit=circuit
    )


SAMPLE_AWS_CREDENTIALS = AWSCredentials(
    endpoint_url=None,
    access_key_id=None,
    secret_access_key=None,
    region_name="us-east-1",
)


def construct_sample_settings() -> job_pb2.JobExecutionSettings:
    return job_pb2.JobExecutionSettings(
        backend="emulator",
        n_shots=1024,
        timeout=Duration(seconds=2),
        role="developer",
    )


def create_dynamodb_client() -> DynamoDBClient:
    return cast(
        "DynamoDBClient",
        boto3.client(
            "dynamodb",
            endpoint_url=SAMPLE_AWS_CREDENTIALS.endpoint_url,
            aws_access_key_id=SAMPLE_AWS_CREDENTIALS.access_key_id,
            aws_secret_access_key=SAMPLE_AWS_CREDENTIALS.secret_access_key,
            region_name=SAMPLE_AWS_CREDENTIALS.region_name,
        ),
    )


@mock_aws
def create_dynamodb_table(table_name: str):
    dynamodb_client = create_dynamodb_client()

    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {"AttributeName": "job_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": DYNAMODB_JOB_TABLE_GSI_NAME,
                "KeySchema": [{"AttributeName": "status", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    dynamodb_client.update_time_to_live(
        TableName=table_name,
        TimeToLiveSpecification={
            "Enabled": True,
            "AttributeName": "job_expiry",
        },
    )
