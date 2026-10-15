import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { BusinessError } from '@kit.BasicServicesKit';
import { notificationManager } from '@kit.NotificationKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { pushService } from '@kit.PushKit';

const DOMAIN: number = 0x5343;
const TAG: string = 'LetterScoutPush';

export default class EntryAbility extends UIAbility {
  onCreate(_want: Want, _launchParam: AbilityConstant.LaunchParam): void {
    pushService.getToken().then((_token: string) => {
      // Never print the token. It is a device identifier and must only be
      // transmitted to the authenticated registration service over HTTPS.
      hilog.info(DOMAIN, TAG, 'Push token acquired; secure registration is pending configuration');
    }).catch((error: BusinessError) => {
      hilog.error(DOMAIN, TAG, 'Push token request failed: %{public}d %{public}s',
        error.code, error.message);
    });
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index', (error: BusinessError) => {
      if (error.code) {
        hilog.error(DOMAIN, TAG, 'Page load failed: %{public}d %{public}s', error.code, error.message);
        return;
      }

      // HarmonyOS requires the page to be loaded before requesting the
      // notification authorization dialog.
      notificationManager.requestEnableNotification(this.context).then(() => {
        hilog.info(DOMAIN, TAG, 'Notification permission is enabled');
      }).catch((permissionError: BusinessError) => {
        hilog.warn(DOMAIN, TAG, 'Notification permission was not enabled: %{public}d %{public}s',
          permissionError.code, permissionError.message);
      });
    });
  }
}
