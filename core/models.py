import uuid
from django.db import models
from django.contrib.auth.models import User


class Team(models.Model):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=5)
    stadium = models.CharField(max_length=100)
    founded_year = models.IntegerField()
    primary_color = models.CharField(max_length=7, default='#333333')
    secondary_color = models.CharField(max_length=7, default='#FFFFFF')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Player(models.Model):
    POSITION_CHOICES = (
        ('GK',  'Goalkeeper'),
        ('DEF', 'Defender'),
        ('MID', 'Midfielder'),
        ('FWD', 'Forward'),
    )

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    position = models.CharField(max_length=3, choices=POSITION_CHOICES)
    price = models.FloatField(help_text='Price in millions')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return f'{name} ({self.team.short_name})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def display_name(self):
        return self.last_name if self.last_name else self.first_name


class Gameweek(models.Model):
    number = models.IntegerField(unique=True)
    deadline = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return f'Gameweek {self.number}'


class Match(models.Model):
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='matches')
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    match_date = models.DateTimeField()
    is_played = models.BooleanField(default=False)

    class Meta:
        ordering = ['match_date']
        verbose_name_plural = 'matches'

    def __str__(self):
        return f'{self.home_team.short_name} vs {self.away_team.short_name} (GW{self.gameweek.number})'


class PlayerStat(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='stats')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_stats')
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)
    clean_sheet = models.BooleanField(default=False)
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    fantasy_points = models.IntegerField(default=0)

    class Meta:
        unique_together = ('player', 'match')

    def save(self, *args, **kwargs):
        self.fantasy_points = self._calculate_points()
        super().save(*args, **kwargs)

    def _calculate_points(self):
        points = 0
        if self.minutes_played >= 60:
            points += 2
        elif self.minutes_played > 0:
            points += 1
        points += self.goals * 6
        points += self.assists * 3
        if self.clean_sheet and self.player.position in ('GK', 'DEF'):
            points += 4
        elif self.clean_sheet and self.player.position == 'MID':
            points += 1
        points -= self.yellow_cards * 1
        points -= self.red_cards * 3
        return points

    def __str__(self):
        return f'{self.player} — {self.match} ({self.fantasy_points} pts)'


class FantasyTeam(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fantasy_teams')
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name='fantasy_teams')
    name = models.CharField(max_length=100)
    total_points = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'gameweek')

    def __str__(self):
        return f'{self.name} — {self.gameweek} ({self.user.username})'


class FantasyPick(models.Model):
    fantasy_team = models.ForeignKey(FantasyTeam, on_delete=models.CASCADE, related_name='picks')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='fantasy_picks')
    is_captain = models.BooleanField(default=False)
    points_scored = models.IntegerField(default=0)

    class Meta:
        unique_together = ('fantasy_team', 'player')

    def __str__(self):
        captain = ' (C)' if self.is_captain else ''
        return f'{self.player}{captain} — {self.fantasy_team}'


class League(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=8, unique=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_leagues')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class LeagueMember(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='league_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('league', 'user')

    def __str__(self):
        return f'{self.user.username} — {self.league.name}'
