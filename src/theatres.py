import trio
import asks
import datetime
import logging
from ratelimit import limits, RateLimitException


API_KEY = '<Your API Key>'
BASE_URL = 'http://data.tmsapi.com/v1.1/theatres'
TODAY = datetime.datetime.today().strftime('%Y-%m-%d')
ONE_SECOND=1

LOG_FILENAME = 'theatres_details.log'
logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG,filemode='w')


class Theatres:
    'A class that contains the get methods for theatres_by_postal_code and theatre_showtimes'

    def __init__(self):
        self.results_list = []
        asks.init(trio)

    async def __asks_theatres_by_postal_code(self, base_url, api_key, zip=10153, radius=10):
        '''method to call tmsapi theatres
        http://developer.tmsapi.com/docs/read/data_v1_1/movies/Theatres_by_postal_code '''
        result = await asks.get(base_url, params={'zip': str(zip),'radius':str(radius),'api_key':api_key})
        return result.json()

    async def __asks_theatre_showtimes(self, base_url, theatre_id, api_key):
        '''method to call tmsapi movie and showtime
        http://developer.tmsapi.com/docs/read/data_v1_1/movies/Theatre_showtimes
        '''
        url = base_url+'/'+str(theatre_id)+'/showings'
        result = await asks.get(url, params={'startDate': TODAY,'api_key':api_key})
        return result.json()

    async def __get_theatres_nyc(self):
        '''get theatres data from Gracenote and check for NY '''
        result_theatre = await self.__asks_theatres_by_postal_code(base_url=BASE_URL, api_key=API_KEY)
        self.results_list = [theater for theater in result_theatre if theater["location"]["address"]['state'] == "NY"]
        return self.results_list

    async def __get_movie_details(self, theatre):
        '''get movie and showtime data from Gracenote and update result_list'''
        try:
            theatre_id_num = theatre['theatreId']
            await self.__enforce_rate_limit()
            result = await self.__asks_theatre_showtimes(base_url=BASE_URL, theatre_id=theatre_id_num, api_key=API_KEY)
            theatre['movies'] = result
        except Exception:
            logging.debug("Request failed for theatreId: %s", theatre_id_num)

    async def __movie_showtime_details(self):
        '''private function to create nursery for each movie'''
        async with trio.open_nursery() as nursery:
            for theatre in self.results_list:
                if theatre.get('theatreId'):
                    nursery.start_soon(self.__get_movie_details, theatre)
            return self.results_list

    def get_theatres(self):
        '''method to get theatres list'''
        return trio.run(self.__get_theatres_nyc)

    def get_theatre_showtimes(self):
        '''method to get movie showtimes result updated to results_list'''
        return trio.run(self.__movie_showtime_details)

    def get_results(self):
        '''method to get result list'''
        return self.results_list

    async def __enforce_rate_limit(self):
        '''rate limit method to ensure 20calls per second'''
        tries = 0
        while True:
            try:
                self.__rate_limiter()
                break
            except RateLimitException as e:
                tries += 1
                remaining = e.period_remaining
                logging.debug("rate limit exceeded (try #%s), sleeping %s", tries, remaining)
                await trio.sleep(remaining)

    @limits(calls=20, period=ONE_SECOND)
    def __rate_limiter(self):
        '''helper method for ratelimit'''
        logging.info("rate limit ok")


if __name__ == '__main__':
    grace_obj = Theatres()
    res_th = grace_obj.get_theatres()
    res = grace_obj.get_theatre_showtimes()
    print("results_list=", res)
    #print("results_list=", grace_obj.get_results())

