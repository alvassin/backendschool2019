"""
REST API сервис, анализирующий рынок для промо-акций.
"""
import argparse
import logging
import os
import pwd
from sys import argv

from aiohttp.web import run_app
from aiomisc import bind_socket
from aiomisc.log import LogFormat, basic_config
from configargparse import ArgumentParser
from setproctitle import setproctitle
from yarl import URL

from analyzer.api.app import create_app
from analyzer.utils.argparse import clear_environ, positive_int
from analyzer.utils.pg import DEFAULT_PG_URL


ENV_VAR_PREFIX = 'ANALYZER_'


parser = ArgumentParser(
    auto_env_var_prefix=ENV_VAR_PREFIX, allow_abbrev=False,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('--user', required=False, type=pwd.getpwnam,
                    help='Change process UID')

group = parser.add_argument_group('API Options')
group.add_argument('--api-address', default='0.0.0.0',
                   help='IPv4/IPv6 address API server would listen on')
group.add_argument('--api-port', type=positive_int, default=8081,
                   help='TCP port API server would listen on')

group = parser.add_argument_group('PostgreSQL options')
group.add_argument('--pg-url', type=URL, default=URL(DEFAULT_PG_URL),
                   help='URL to use to connect to the database')
group.add_argument('--pg-pool-min-size', type=int, default=10,
                   help='Minimum database connections')
group.add_argument('--pg-pool-max-size', type=int, default=10,
                   help='Maximum database connections')

group = parser.add_argument_group('Logging options')
group.add_argument('--log-level', default='info',
                   choices=('debug', 'info', 'warning', 'error', 'fatal'))
group.add_argument('--log-format', choices=LogFormat.choices(),
                   default='color')


def main():
    args = parser.parse_args()

    # После получения конфигурации приложения переменные окружения приложения
    # больше не нужны и даже могут представлять опасность - например, они могут
    # случайно "утечь" с отображением информации об ошибке. Злоумышленники
    # в первую очередь будут пытаться получить информацию об окружении, очистка
    # переменных окружения считается хорошим тоном.

    # Python позволяет управлять поведением stdlib модулей с помощью
    # многочисленных переменных окружения, разумно очищать переменные окружения
    # по префиксу приложения, указанного в ConfigArgParser.
    clear_environ(lambda i: i.startswith(ENV_VAR_PREFIX))

    # Чтобы логи не блокировали основной поток (и event loop) во время операций
    # записи в stderr или файл - логи можно буфферизовать и обрабатывать в
    # отдельном потоке (aiomisc.basic_config настроит буфферизацию
    # автоматически).
    basic_config(args.log_level, args.log_format, buffered=True)

    # Аллоцируем сокет из под привиллегированного пользователя отдельным шагом,
    # чтобы была возможность перед запуском приложения сменить пользователя ОС.
    sock = bind_socket(address=args.api_address, port=args.api_port,
                       proto_name='http')

    # После того как приложение аллоцировало сокет и ему больше не нужны
    # привиллегии - хорошим решением будет сменить пользователя (например,
    # на nobody, у которого нет никаких специальных привиллегий) - это также
    # усложнит жизнь злоумышленникам.
    if args.user is not None:
        logging.info('Changing user to %r', args.user.pw_name)
        os.setgid(args.user.pw_gid)
        os.setuid(args.user.pw_uid)

    # В списке процессов намного удобнее видеть название текущего приложения
    setproctitle(os.path.basename(argv[0]))

    app = create_app(args)
    run_app(app, sock=sock)


if __name__ == '__main__':
    main()
