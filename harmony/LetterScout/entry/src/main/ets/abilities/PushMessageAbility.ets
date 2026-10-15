import { UIAbility } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { pushService } from '@kit.PushKit';

const DOMAIN: number = 0x5343;
const TAG: string = 'LetterScoutPush';

interface LetterNotificationData {
  doi?: string;
  specialty?: string;
  journal?: string;
}

export default class PushMessageAbility extends UIAbility {
  onCreate(): void {
    try {
      // DEFAULT is the notification-message channel. This must be registered
      // synchronously when the ability is created.
      pushService.receiveMessage('DEFAULT', this, (payload) => {
        try {
          const data: string = payload.data;
          const paper: LetterNotificationData = JSON.parse(data) as LetterNotificationData;
          hilog.info(DOMAIN, TAG,
            'Notification received for specialty=%{public}s journal=%{public}s',
            paper.specialty ?? 'unknown', paper.journal ?? 'unknown');
        } catch (error) {
          const businessError: BusinessError = error as BusinessError;
          hilog.error(DOMAIN, TAG, 'Notification payload processing failed: %{public}d %{public}s',
            businessError.code, businessError.message);
        }
      });
    } catch (error) {
      const businessError: BusinessError = error as BusinessError;
      hilog.error(DOMAIN, TAG, 'Notification listener registration failed: %{public}d %{public}s',
        businessError.code, businessError.message);
    }
  }
}
