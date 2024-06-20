# Dockerised Python Translation Tool

This project is a Dockerised Python tool designed to work with the Weblate API to fetch projects and use ChatGPT AI to translate them. The updated translations are then committed back to Weblate.

You can see an example of AI translation in your language by visiting *https://ubys.org/\<languege code\>/translator/*

For example:
1. English https://ubys.org/en/translator/
2. Spanish https://ubys.org/es/translator/
3. French https://ubys.org/fr/translator/
4. German https://ubys.org/de/translator/
5. Chinese https://ubys.org/zh/translator/
6. Japanese https://ubys.org/ja/translator/
7. Korean https://ubys.org/ko/translator/
8. Italian https://ubys.org/it/translator/
9. Portuguese https://ubys.org/pt/translator/
10. Arabic https://ubys.org/ar/translator/



## Table of Contents
- [Installation](#installation)
- [Usage](#usage)
  - [Using Dev Container](#using-dev-container)
  - [Using Docker Container](#using-docker-container)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Installation

To use this project, you need to have the following installed on your machine:
- [Docker](https://www.docker.com/get-started)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Python](https://www.python.org/downloads/)

## Usage

### Using Dev Container

1. Clone the repository:

2. Open the project in Visual Studio Code. You will be prompted to reopen the project in a Dev Container. Choose `Reopen in Container`.

3. Create a `.env` file in the root of the project with the following fields:

    ```sh
    WEBLATE_API_URL=<your_weblate_api_url>
    WEBLATE_API_KEY=<your_weblate_api_key>
    OPENAI_KEY=<your_openai_key>
    ```

4. Modify the VSCode launch configuration (`.vscode/launch.json`) if needed.

5. Run the Python configuration in VSCode to start the tool.

### Using Docker Container

1. Build the Docker image:

    ```sh
    docker build -f translator.dockerfile -t translation-tool .
    ```

2. Run the Docker container with the required environment variables:

    ```sh
    docker run -e WEBLATE_API_URL="<your_weblate_api_url>" \
           -e WEBLATE_API_KEY="<your_weblate_api_key>" \
           -e OPENAI_KEY="<your_openai_key>" \
           translation-tool --project <project_name> --components <component_name> --languages <language_code>
    ```

## Configuration

The project requires a `.env` file with the following fields to be set:

```sh
WEBLATE_API_URL=<your_weblate_api_url>
WEBLATE_API_KEY=<your_weblate_api_key>
OPENAI_KEY=<your_openai_key>
