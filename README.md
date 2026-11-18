# Jogo da Forca P2P

Projeto  para a disciplina de Redes de Computadores. Implementação de um cliente P2P (Peer-to-Peer) do  Jogo da Forca. O sistema opera de forma descentralizada, utilizando um servidor Rendezvous apenas para registro e descoberta inicial de peers, enquanto toda a comunicação de lobby e o andamento das partidas ocorrem diretamente entre os nós por meio de conexões TCP persistentes.

## Grupo 9 — Integrantes

- Arthur Correia Marques — 241022316
- Gustavo Pires dos Santos — 251004349
- Helton Rodrigues da Silva Junior — 251021789

## Executar no Linux

No terminal, a partir da pasta raiz do projeto:

```bash
python3 --version
python3 src/main.py
```

O programa carrega `config.json` automaticamente. Para encerrar, use `/quit` ou `Ctrl+C`.

## Configuração

Edite `config.json` antes de iniciar o programa. Os campos mais importantes são:

| Campo | Descrição |
| --- | --- |
| `name` | Nome deste peer. |
| `namespace` | Namespace usado para agrupar e descobrir peers. |
| `listen_port` | Porta TCP em que este peer aceita conexões. |
| `rdv_host` e `rdv_port` | Endereço e porta do servidor Rendezvous. |
| `register_ttl` | Tempo de validade do registro, em segundos. |
| `discover_interval` | Intervalo entre ciclos de descoberta, em segundos. |
| `ping_interval` e `ping_miss_limit` | Intervalo e limite de falhas do keep-alive. |
| `max_reconnect_attempts`, `base_backoff` e `max_backoff` | Parâmetros de tentativas e espera para reconexão. |
| `lives`, `max_players` e `turn_timeout` | Regras padrão das partidas. |
| `words_file` | Arquivo usado para sortear palavras em `/create --random`. |
| `log_file` | Arquivo para gravar logs.





## Comandos da CLI

Digite `/help` dentro do programa para ver a ajuda. Os comandos disponíveis são:

| Comando | Ação |
| --- | --- |
| `/peers [* \| #namespace]` | Descobre e lista peers; sem argumento, usa o namespace local. |
| `/conn` | Lista conexões ativas, direção, estado e RTT. |
| `/rtt` | Mostra o RTT médio disponível por peer. |
| `/reconnect` | Força uma nova reconciliação com o Rendezvous. |
| `/games` | Consulta os vizinhos sobre partidas disponíveis. |
| `/create <palavra> [max_players]` | Cria uma partida hospedada por você. |
| `/create --random [max_players]` | Cria uma partida com palavra sorteada do arquivo configurado. |
| `/start` | Inicia a partida hospedada; é necessário ao menos um jogador. |
| `/cancel` | Cancela a partida hospedada. |
| `/join <host_peer_id>` | Entra em uma partida, por exemplo: `/join alice@CIC`. |
| `/leave` | Sai da partida atual. |
| `/guess <letra>` | Envia um palpite de letra. |
| `/word <palavra>` | Envia um palpite da palavra inteira. |
| `/status` | Mostra o estado local da partida. |
| `/log <DEBUG\|INFO\|WARNING\|ERROR>` | Altera o nível de log. |
| `/quit` | Encerra o programa e a participação na partida, se houver. |


## Estrutura do projeto

```text
src/
├── conections/   # Conexões TCP, Rendezvous, descoberta e keep-alive
├── game/         # Regras e estado das partidas
├── interface/    # CLI e configuração de logs
└── main.py       # Inicialização do peer
tests/            # Testes automatizados
config.json       # Configuração local do peer
```
