# スケジューラーサーバ

## Introduction

スケジューラサーバはユーザーから送られてくるジョブを管理し、実行するジョブを実機サーバに送るためのサーバです。スケジューラサーバは AWS で稼働し、主に次の機能を提供します。

- ユーザーから回路表現・グラフ表現・実機表現を受け取り、ジョブとして管理する
- ジョブのステータスを管理する
- ユーザーにジョブのステータスや実行時の情報を返す
- ユーザーにジョブの実行結果を取得するためのURLを返す
- 実機のサーバからリクエストを受け取り、実行するジョブを渡す
- 実機のサーバから送られてきたジョブ実行の成否をジョブ管理システムで記録する
- 実機のサーバに対して実行結果をアップロードするための署名付きURLを発行する

## Requirements

- プラットフォーム
  - Linux (Ubuntu 24.04 LTS 推奨)
- Python バージョン
  - 3.10, 3.11, 3.12, 3.13

### Dependencies

スケジューラサーバでは以下の外部モジュールを使用しています。

```toml
protobuf = "5.29.3"
grpcio = "1.71.0"
grpcio-tools = "1.71.0"
grpcio-health-checking = "1.71.0"
boto3 = "1.34.129"
mypy-boto3-dynamodb = "1.39.0"
```

また、開発では上記に加えて以下のモジュールを使用しています。

```toml
pytest
moto = {extras = ["s3"], version = "5.0.9"}
pytest-mock
allpairspy
mqc3 >= "1.0.0"
```

開発環境構築には [Pipenv](https://pipenv.pypa.io/en/latest/) を使用しています。  
[公式ガイド](https://pipenv.pypa.io/en/latest/installation.html) に従って Pipenv をインストールしてください。  
Pipenv を使用して開発環境を構築するためには以下のコマンドを実行してください。

```sh
pipenv install --python </path/to/python/executable> --dev
```

### Architecture Dependencies

スケジューラサーバは以下の AWS サービスに依存しています。  

- S3
  - ジョブの入力および出力を一時的に保存するために使用
- Dynamo DB
  - ジョブの状態や実行時の情報を管理するために使用
- SSM Parameter Store
  - S3のバケット名やDynamoDBのテーブル名等を取得する際に使用

また、スケジューラサーバはユーザーから送られてきたリクエストに含まれるトークンの認証を行います。  
認証の際にトークンの情報を取得するためにトークンデータベースサーバにアクセスします。  
`proto/mqc3_cloud/token_database/token_database.proto` に定義されている rpc を実装したサーバを用意してください。

## Usage

Pipenv で環境構築後、以下のコマンドを実行することで仮想環境でスケジューラサーバを起動することができます。

```sh
pipenv run python3 scheduler.py \
--port-for-submission ${MQC3_SUBMISSION_SERVER_PORT} --port-for-execution ${MQC3_EXECUTION_SERVER_PORT} \
--address_to_token_database ${MQC3_TOKEN_DATABASE_ADDRESS} \
-k ${AWS_ACCESS_KEY_ID} -s ${AWS_SECRET_ACCESS_KEY} --region ${AWS_REGION} \
--job_bucket_name_key ${JOB_BUCKET_NAME_KEY} --job_table_name_key ${JOB_TABLE_NAME_KEY} --backend_status_parameter_name ${BACKEND_STATUS_PARAMETER_NAME} \
--endpoint ${ENDPOINT} --s3_endpoint ${S3_ENDPOINT} \
[--unify-backend] [--dev]
```

各オプションについては以下の通りです。

| オプション                        | 説明                                                                                               |
| --------------------------------- | -------------------------------------------------------------------------------------------------- |
| `--port-for-submission`           | クライアントがスケジューラーサーバと通信する際に使用するポート                                     |
| `--port-for-execution`            | 実機サーバがスケジューラーサーバと通信する際に使用するポート                                       |
| `--address_to_token_database`     | トークンデータベースのサーバアドレス                                                               |
| `--aws_access_key_id`             | AWS のアクセスキー                                                                                 |
| `--aws_secret_access_key`         | AWS のシークレットアクセスキー                                                                     |
| `--region`                        | AWS リージョン                                                                                     |
| `--job_bucket_name_key`           | SSM Parameter Store からジョブの入出力を保存するバケット名を取得する際に使用するキー名             |
| `--job_bucket_name_key`           | SSM Parameter Store からジョブの状態を管理するDynamoDB テーブル名を取得する際に使用するキー名      |
| `--backend_status_parameter_name` | SSM Parameter Store からバックエンドの状態を指定する TOML 形式の文字列を取得する際に使用するキー名 |
| `--endpoint`                      | AWS サービスのエンドポイントURL。設定する際は `--dev` オプションをつける必要があります。           |
| `--s3_endpoint`                   | S3 のエンドポイントURL。設定する際は `--dev` オプションをつける必要があります。                    |
| `--unify_backends`                | ジョブを実行する際に指定される backend を統一して扱う際につけるフラグ                              |
| `--dev`                           | 開発時にAWS のサービスではなく LocalStack 等を利用してサーバを起動する際につけるフラグ             |

また、次の環境変数を変更することで scheduler に関するオプションを設定できます。

| 環境変数                                  | 説明                                                                    |
| ----------------------------------------- | ----------------------------------------------------------------------- |
| `SCHEDULER_SUBMISSION_MAX_WORKERS`        | submission service のワーカー数。デフォルト 100。                       |
| `SCHEDULER_EXECUTION_MAX_WORKERS`         | execution service のワーカー数。デフォルト 10。                         |
| `SCHEDULER_SUBMISSION_MAX_MESSAGE_LENGTH` | submission service の gRPC のメッセージサイズの上限。デフォルト 10MB。  |
| `SCHEDULER_EXECUTION_MAX_MESSAGE_LENGTH`  | execution service の gRPC のメッセージサイズの上限。デフォルト 10MB。   |
| `SCHEDULER_MAX_QUEUE_BYTES`               | ジョブキューのメモリ使用量の上限（バイト数）。デフォルト 100MB。        |
| `SCHEDULER_MAX_CONCURRENT_JOBS_ADMIN`     | ADMIN が同時に実行できるジョブの上限。デフォルト 1000。                 |
| `SCHEDULER_MAX_CONCURRENT_JOBS_DEVELOPER` | DEVELOPER が同時に実行できるジョブの上限。デフォルト 10。               |
| `SCHEDULER_MAX_CONCURRENT_JOBS_GUEST`     | GUEST が同時に実行できるジョブの上限。デフォルト 5。                    |
| `SCHEDULER_MAX_JOB_BYTES_ADMIN`           | ADMIN が実行できるジョブサイズの上限（バイト数）。デフォルト 10MB。     |
| `SCHEDULER_MAX_JOB_BYTES_DEVELOPER`       | DEVELOPER が実行できるジョブサイズの上限（バイト数）。デフォルト 10MB。 |
| `SCHEDULER_MAX_JOB_BYTES_GUEST`           | GUEST が実行できるジョブサイズの上限（バイト数）。デフォルト 1MB。      |

## Test

ジョブ管理システムとサーバーの単体テストを行うためには、Pipenv で開発環境を構築し、以下のコマンドを実行してください。

```sh
pipenv run pytest
```

## Source Tree

```sh
$ tree -L 1 --dirsfirst
.
├── backend_manager       : サーバの状態を管理するモジュール
├── job_manager           : ジョブ管理システムのモジュール
├── message_manager       : ジョブのステータスメッセージを管理するモジュール
├── pb                    : protocol buffer の定義ファイル (自動生成)
├── proto                 : protocol buffer
├── test                  : テスト
├── LICENSE               : ライセンスファイル
├── Pipfile               : pipenv 用の設定ファイル
├── README.md             : readme ドキュメント
├── __init__.py           : モジュールの初期化ファイル
├── __version__.py        : スケジューラーサーバのバージョン定義ファイル
├── get_token_info.py     : トークンデータベースからトークン情報を取得するモジュール
├── server.py             : スケジューラーサーバのメイン
├── server_execution.py   : スケジューラーと物理ラボ層の間の通信を行うサーバモジュール
├── server_submission.py  : ユーザーとスケジューラーの間の通信を行うサーバモジュール
└── utility.py            : ユーティリティ関数モジュール

7 directories, 10 files
```
