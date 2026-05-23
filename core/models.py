"""
MatchDay — Tournament Registration & Management System
=======================================================
Models for managing tournaments, teams, players, matches, and standings.

ROLES:
  - Super Admin  (is_superuser=True)  → Full Django admin access
  - Tournament Admin (is_staff=True)  → Creates tournaments, enters match stats
  - Coach (regular User)              → Registers team/players, views standings
"""
import uuid
from django.db import models
from django.contrib.auth.models import User


# ─────────────────────────────────────────────────────────────────────────────
# TEAM & PLAYER — Core data entities
# ─────────────────────────────────────────────────────────────────────────────

class Team(models.Model):
    """
    A football team managed by a Coach (regular user).
    Each team belongs to exactly one coach.
    """
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=5)
    primary_color = models.CharField(max_length=7, default='#333333')
    secondary_color = models.CharField(max_length=7, default='#FFFFFF')
    coach = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='teams',
        null=True, blank=True,
        help_text='The coach (regular user) who owns this team.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Player(models.Model):
    """
    A player belonging to a team. Players cannot appear in multiple teams.
    """
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
    jersey_number = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['jersey_number', 'last_name']

    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return f'{name} ({self.team.short_name})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def display_name(self):
        return self.last_name if self.last_name else self.first_name


# ─────────────────────────────────────────────────────────────────────────────
# TOURNAMENT — The central organizing entity
# ─────────────────────────────────────────────────────────────────────────────

class Tournament(models.Model):
    """
    A tournament created by a Tournament Admin (is_staff=True).
    Can be either LEAGUE (round-robin) or KNOCKOUT format.
    """
    FORMAT_CHOICES = (
        ('LEAGUE', 'League'),
        ('KNOCKOUT', 'Knockout'),
    )
    STATUS_CHOICES = (
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
    )

    name = models.CharField(max_length=200)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='LEAGUE')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='managed_tournaments',
        help_text='The Tournament Admin who created this tournament.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_format_display()})'


class TournamentTeam(models.Model):
    """
    Many-to-many through table: which teams are registered in which tournament.
    """
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='tournament_teams')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='tournament_entries')
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tournament', 'team')
        ordering = ['registered_at']

    def __str__(self):
        return f'{self.team.name} in {self.tournament.name}'


# ─────────────────────────────────────────────────────────────────────────────
# MATCH & PLAYER STATS — Fixtures and per-player performance data
# ─────────────────────────────────────────────────────────────────────────────

class Match(models.Model):
    """
    A single match within a tournament.
    round_label is flexible: "Matchday 1", "Quarter-Final", "Semi-Final", "Final", etc.
    """
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    round_label = models.CharField(max_length=50, default='Matchday 1')
    match_date = models.DateTimeField(null=True, blank=True)
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    is_played = models.BooleanField(default=False)

    class Meta:
        ordering = ['round_label', 'match_date']
        verbose_name_plural = 'matches'

    def __str__(self):
        return f'{self.home_team.short_name} vs {self.away_team.short_name} ({self.round_label})'


class PlayerStat(models.Model):
    """
    Per-player statistics for a single match.
    Entered by the Tournament Admin after a match is played.
    """
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='stats')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_stats')
    goals = models.IntegerField(default=0)
    assists = models.IntegerField(default=0)
    yellow_cards = models.IntegerField(default=0)
    red_cards = models.IntegerField(default=0)
    minutes_played = models.IntegerField(default=0)

    class Meta:
        unique_together = ('player', 'match')

    def __str__(self):
        return f'{self.player} — {self.match} (G:{self.goals} A:{self.assists})'


# ─────────────────────────────────────────────────────────────────────────────
# STANDING — Denormalized league table (computed by backend)
# ─────────────────────────────────────────────────────────────────────────────

class Standing(models.Model):
    """
    Denormalized league table row for a team within a tournament.
    IMPORTANT: This table is COMPUTED, not manually edited.
    The backend function `recompute_standings()` in standings.py recalculates
    all rows whenever a Tournament Admin enters or updates a match result.

    ═══ WHY DENORMALIZE? ═══
    Computing standings on every page load would require iterating through
    ALL matches every time. By saving pre-computed results, we trade a small
    write cost for fast reads — a classic database optimization pattern.
    """
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='standings')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='standings')
    played = models.IntegerField(default=0)
    won = models.IntegerField(default=0)
    drawn = models.IntegerField(default=0)
    lost = models.IntegerField(default=0)
    goals_for = models.IntegerField(default=0)
    goals_against = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    points = models.IntegerField(default=0)

    class Meta:
        unique_together = ('tournament', 'team')
        ordering = ['-points', '-goal_difference', '-goals_for']

    def __str__(self):
        return f'{self.team.name} — {self.points} pts ({self.tournament.name})'


# ─────────────────────────────────────────────────────────────────────────────
# KNOCKOUT BRACKET — For KO-style tournaments
# ─────────────────────────────────────────────────────────────────────────────

class KnockoutRound(models.Model):
    """
    Represents a round in a knockout tournament (e.g., Quarter-Final, Semi-Final, Final).
    """
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='knockout_rounds')
    round_name = models.CharField(max_length=50)  # e.g., "Quarter-Final"
    round_order = models.IntegerField(default=0)  # 1=QF, 2=SF, 3=Final

    class Meta:
        ordering = ['round_order']

    def __str__(self):
        return f'{self.round_name} — {self.tournament.name}'


class KnockoutFixture(models.Model):
    """
    A single fixture within a knockout round.
    The winner advances to the next round.
    """
    round = models.ForeignKey(KnockoutRound, on_delete=models.CASCADE, related_name='fixtures')
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='knockout_fixture', null=True, blank=True)
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ko_home', null=True, blank=True)
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='ko_away', null=True, blank=True)
    winner = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='ko_wins')

    def __str__(self):
        h = self.home_team.short_name if self.home_team else 'TBD'
        a = self.away_team.short_name if self.away_team else 'TBD'
        return f'{h} vs {a} ({self.round.round_name})'
