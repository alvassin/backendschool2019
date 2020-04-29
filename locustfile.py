import logging
from http import HTTPStatus

from locust import HttpLocust, TaskSet, constant, task
from locust.exception import RescheduleTask

from analyzer.api.handlers import (
    CitizenBirthdaysView, CitizensView, CitizenView, TownAgeStatView,
)
from analyzer.utils.testing import generate_citizen, generate_citizens, url_for


class AnalyzerTaskSet(TaskSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.round = 0

    def make_dataset(self):
        citizens = [
            # Первого жителя создаем с родственником. В запросе к
            # PATCH-обработчику список relatives будет содержать только другого
            # жителя, что потребует выполнения максимального кол-ва запросов
            # (как на добавление новой родственной связи, так и на удаление
            # существующей).
            generate_citizen(citizen_id=1, relatives=[2]),
            generate_citizen(citizen_id=2, relatives=[1]),
            *generate_citizens(citizens_num=9998, relations_num=1000,
                               start_citizen_id=3)
        ]
        return {citizen['citizen_id']: citizen for citizen in citizens}

    def request(self, method, path, expected_status, **kwargs):
        with self.client.request(
                method, path, catch_response=True, **kwargs
        ) as resp:
            if resp.status_code != expected_status:
                resp.failure(f'expected status {expected_status}, '
                             f'got {resp.status_code}')
            logging.info(
                'round %r: %s %s, http status %d (expected %d), took %rs',
                self.round, method, path, resp.status_code, expected_status,
                resp.elapsed.total_seconds()
            )
            return resp

    def create_import(self, dataset):
        resp = self.request('POST', '/imports', HTTPStatus.CREATED,
                            json={'citizens': list(dataset.values())})
        if resp.status_code != HTTPStatus.CREATED:
            raise RescheduleTask
        return resp.json()['data']['import_id']

    def get_citizens(self, import_id):
        url = url_for(CitizensView.URL_PATH, import_id=import_id)
        self.request('GET', url, HTTPStatus.OK,
                     name='/imports/{import_id}/citizens')

    def update_citizen(self, import_id):
        url = url_for(CitizenView.URL_PATH, import_id=import_id, citizen_id=1)
        self.request('PATCH', url, HTTPStatus.OK,
                     name='/imports/{import_id}/citizens/{citizen_id}',
                     json={'relatives': [i for i in range(3, 10)]})

    def get_birthdays(self, import_id):
        url = url_for(CitizenBirthdaysView.URL_PATH, import_id=import_id)
        self.request('GET', url, HTTPStatus.OK,
                     name='/imports/{import_id}/citizens/birthdays')

    def get_town_stats(self, import_id):
        url = url_for(TownAgeStatView.URL_PATH, import_id=import_id)
        self.request('GET', url, HTTPStatus.OK,
                     name='/imports/{import_id}/towns/stat/percentile/age')

    @task
    def workflow(self):
        self.round += 1
        dataset = self.make_dataset()

        import_id = self.create_import(dataset)
        self.get_citizens(import_id)
        self.update_citizen(import_id)
        self.get_birthdays(import_id)
        self.get_town_stats(import_id)


class WebsiteUser(HttpLocust):
    task_set = AnalyzerTaskSet
    wait_time = constant(1)
