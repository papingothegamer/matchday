from django.core.management.base import BaseCommand
from core.models import Gameweek, FantasyTeam, FantasyPick
from django.db import transaction

class Command(BaseCommand):
    help = 'Executes the Gameweek Rollover: Clones teams, resets hits, and grants free transfers.'

    def handle(self, *args, **kwargs):
        active_gw = Gameweek.objects.filter(is_active=True).first()
        if not active_gw:
            self.stdout.write(self.style.ERROR('❌ No active Gameweek found.'))
            return

        next_gw = Gameweek.objects.filter(number=active_gw.number + 1).first()
        if not next_gw:
            self.stdout.write(self.style.WARNING(f'⚠️ No Gameweek {active_gw.number + 1} found. Season is over!'))
            return

        self.stdout.write(f'🔄 Initiating Rollover: GW{active_gw.number} -> GW{next_gw.number}...')

        with transaction.atomic():
            current_teams = FantasyTeam.objects.filter(gameweek=active_gw)
            count = 0
            
            for team in current_teams:
                # FPL Rules: Users get +1 Free Transfer, up to a maximum of 2.
                new_ft = min(2, team.free_transfers + 1)

                # Create the fresh team for the new gameweek
                new_team, created = FantasyTeam.objects.get_or_create(
                    user=team.user,
                    gameweek=next_gw,
                    defaults={
                        'formation': team.formation,
                        'bank': team.bank,
                        'free_transfers': new_ft,
                        'points_hit': 0 # Reset points hits for the new week
                    }
                )

                if created:
                    # Clone the 15-man roster, preserving purchase prices
                    for pick in team.picks.all():
                        FantasyPick.objects.create(
                            fantasy_team=new_team,
                            player=pick.player,
                            is_captain=pick.is_captain,
                            is_sub=pick.is_sub,
                            purchase_price=pick.purchase_price
                        )
                    count += 1

            # Advance the global clock
            active_gw.is_active = False
            active_gw.save()

            next_gw.is_active = True
            next_gw.save()

            self.stdout.write(self.style.SUCCESS(f'✅ Rollover Complete! Cloned {count} teams. GW{next_gw.number} is now active.'))
